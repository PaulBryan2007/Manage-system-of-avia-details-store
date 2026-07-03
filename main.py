from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///warehouse.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Для flash-сообщений
db = SQLAlchemy(app)

MAX_CAPACITY = 10  # Максимальная вместимость одной ячейки


# ==================== МОДЕЛИ БАЗЫ ДАННЫХ ====================

class Article(db.Model):
    """Модель для хранения информации о каждой поставке/запчасти"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    article = db.Column(db.String(30), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    cell = db.Column(db.String(10), nullable=False)
    #created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Cell(db.Model):
    """Модель для хранения состояния ячеек склада"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(10), unique=True, nullable=False)
    part_name = db.Column(db.String(50), nullable=True)
    article = db.Column(db.String(30), nullable=True)
    quantity = db.Column(db.Integer, default=0)


# ==================== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ====================

with app.app_context():
    db.create_all()
    # Создаём ячейки склада 3x3 (ряды A, B, C и колонки 1, 2, 3)
    if Cell.query.count() == 0:
        for row in ['A', 'B', 'C']:
            for col in ['1', '2', '3']:
                db.session.add(Cell(name=f"{row}{col}"))
        db.session.commit()
        print("✅ Создано 9 ячеек склада: A1, A2, A3, B1, B2, B3, C1, C2, C3")


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def find_best_cell(name, article, quantity):
    """
    Находит лучшую ячейку для размещения запчасти согласно приоритетам:

    ПРИОРИТЕТ 1: Ячейка с ТАКОЙ ЖЕ запчастью и свободным местом
    ПРИОРИТЕТ 2: ЛЮБАЯ частично заполненная ячейка (для экономии места)
    ПРИОРИТЕТ 3: ПОЛНОСТЬЮ ПУСТАЯ ячейка

    Возвращает: объект Cell или None, если ячейка не найдена
    """

    # ПРИОРИТЕТ 1: Поиск ячейки с такой же деталью и свободным местом
    for cell in Cell.query.all():
        if (cell.part_name == name and
                cell.article == article and
                cell.quantity + quantity <= MAX_CAPACITY):
            print(f"🎯 Приоритет 1: Ячейка {cell.name} - такая же деталь {name} ({cell.quantity}/{MAX_CAPACITY})")
            return cell

    # ПРИОРИТЕТ 2: Поиск любой частично заполненной ячейки
    for cell in Cell.query.all():
        if (cell.part_name is not None and
                cell.quantity + quantity <= MAX_CAPACITY):
            print(
                f"🎯 Приоритет 2: Ячейка {cell.name} - частично заполнена ({cell.quantity}/{MAX_CAPACITY}, {cell.part_name})")
            return cell

    # ПРИОРИТЕТ 3: Поиск полностью пустой ячейки
    for cell in Cell.query.all():
        if cell.part_name is None:
            print(f"🎯 Приоритет 3: Ячейка {cell.name} - пустая")
            return cell

    # Ячейка не найдена - склад переполнен
    print(f"❌ Нет подходящей ячейки для {quantity} шт. {name}")
    return None


# ==================== МАРШРУТЫ (ROUTES) ====================

@app.route('/', methods=['POST', 'GET'])
def index():
    """Главная страница - добавление новых запчастей"""

    if request.method == 'POST':
        name = request.form['name'].strip()
        article = request.form['article'].strip()

        try:
            quantity = int(request.form['quantity'])
        except ValueError:
            flash("❌ Ошибка: количество должно быть числом!", "danger")
            return redirect(url_for('index'))

        # Валидация входных данных
        if not name or not article:
            flash("❌ Ошибка: название и артикул не могут быть пустыми!", "danger")
            return redirect(url_for('index'))

        if quantity <= 0:
            flash("❌ Ошибка: количество должно быть больше 0!", "danger")
            return redirect(url_for('index'))

        if quantity > MAX_CAPACITY:
            flash(f"❌ Ошибка: за одну поставку нельзя принять больше {MAX_CAPACITY} шт.!", "danger")
            return redirect(url_for('index'))

        # Поиск лучшей ячейки для размещения
        target_cell = find_best_cell(name, article, quantity)

        if target_cell:
            # Создаём запись о поступлении
            new_article = Article(
                name=name,
                article=article,
                quantity=quantity,
                cell=target_cell.name
            )
            db.session.add(new_article)

            # Обновляем состояние ячейки
            if target_cell.part_name is None:
                # Пустая ячейка - просто заполняем
                target_cell.part_name = name
                target_cell.article = article
                target_cell.quantity = quantity
                flash(f"✅ Размещено {quantity} шт. '{name}' в ячейке {target_cell.name}", "success")
            else:
                # Ячейка уже занята - добавляем количество
                target_cell.quantity += quantity
                flash(
                    f"✅ Добавлено +{quantity} шт. '{name}' в ячейку {target_cell.name}. Теперь {target_cell.quantity}/{MAX_CAPACITY} шт.",
                    "success")

            db.session.commit()
            return redirect(url_for('warehouse'))
        else:
            # Нет подходящей ячейки
            flash(f"❌ Склад переполнен! Нет места для {quantity} шт. '{name}'", "danger")
            return redirect(url_for('index'))

    # GET запрос - показываем форму и статус ячеек
    cells = Cell.query.order_by(Cell.name).all()
    return render_template('index.html', cells=cells, max_capacity=MAX_CAPACITY)


@app.route('/warehouse')
def warehouse():
    """Страница со списком всех запчастей на складе"""
    articles = Article.query.order_by(Article.created_at.desc()).all()
    return render_template('warehouse.html', articles=articles, max_capacity=MAX_CAPACITY)


@app.route('/grid')
def grid():
    """Страница с картой склада (визуализация ячеек)"""
    cells = Cell.query.order_by(Cell.name).all()

    # Группировка по рядам для табличного отображения
    grid_data = {
        'A': [],
        'B': [],
        'C': []
    }

    for cell in cells:
        row = cell.name[0]
        if row in grid_data:
            grid_data[row].append(cell)

    return render_template('grid.html', grid=grid_data, max_capacity=MAX_CAPACITY)


@app.route('/delete/<int:id>')
def delete(id):
    """
    Полное удаление запчасти (удаление всей позиции)
    """
    article = Article.query.get_or_404(id)
    cell_name = article.cell
    cell = Cell.query.filter_by(name=cell_name).first()

    removed_quantity = article.quantity
    article_name = article.name

    if cell:
        # Уменьшаем количество в ячейке
        cell.quantity -= removed_quantity

        # Если ячейка опустела - очищаем её
        if cell.quantity <= 0:
            cell.part_name = None
            cell.article = None
            cell.quantity = 0
            flash(f"🗑️ Ячейка {cell_name} стала пустой", "info")
        else:
            # Если в ячейке остались другие запчасти - определяем доминирующую
            articles_in_cell = Article.query.filter_by(cell=cell_name).all()
            remaining_articles = [a for a in articles_in_cell if a.id != id]
            if remaining_articles:
                sorted_articles = sorted(remaining_articles, key=lambda x: x.quantity, reverse=True)
                main_article = sorted_articles[0]
                cell.part_name = main_article.name
                cell.article = main_article.article

    # Удаляем запись о запчасти
    db.session.delete(article)
    db.session.commit()

    flash(f"✅ Полностью удалена запчасть '{article_name}' ({removed_quantity} шт.)", "success")
    return redirect(url_for('warehouse'))


@app.route('/delete_partial/<int:id>', methods=['POST'])
def delete_partial(id):
    """
    Частичное удаление запчасти (контролируемое количество)
    """
    article = Article.query.get_or_404(id)

    try:
        quantity_to_remove = int(request.form['quantity_to_remove'])
    except ValueError:
        flash("❌ Ошибка: количество должно быть числом!", "danger")
        return redirect(url_for('warehouse'))

    # Проверки
    if quantity_to_remove <= 0:
        flash("❌ Ошибка: количество для удаления должно быть больше 0!", "danger")
        return redirect(url_for('warehouse'))

    if quantity_to_remove > article.quantity:
        flash(f"❌ Ошибка: нельзя удалить {quantity_to_remove} шт., в наличии только {article.quantity} шт.!", "danger")
        return redirect(url_for('warehouse'))

    cell = Cell.query.filter_by(name=article.cell).first()

    if quantity_to_remove == article.quantity:
        # Удаляем всю запчасть целиком
        if cell:
            cell.quantity -= quantity_to_remove
            if cell.quantity <= 0:
                cell.part_name = None
                cell.article = None
                cell.quantity = 0
        db.session.delete(article)
        flash(f"✅ Полностью удалена запчасть '{article.name}' ({quantity_to_remove} шт.)", "success")
    else:
        # Удаляем только часть
        article.quantity -= quantity_to_remove
        if cell:
            cell.quantity -= quantity_to_remove
        flash(f"✅ Удалено {quantity_to_remove} шт. из '{article.name}'. Осталось: {article.quantity} шт.", "success")

    db.session.commit()
    return redirect(url_for('warehouse'))


@app.route('/clear_cell/<cell_name>')
def clear_cell(cell_name):
    """
    Очистка всей ячейки (удаление всех запчастей из указанной ячейки)
    """
    cell = Cell.query.filter_by(name=cell_name).first_or_404()
    articles = Article.query.filter_by(cell=cell_name).all()

    if not articles:
        flash(f"⚠️ Ячейка {cell_name} уже пуста!", "warning")
        return redirect(url_for('grid'))

    # Подсчёт общего количества удаляемого
    total_removed = sum(a.quantity for a in articles)
    articles_count = len(articles)

    # Удаляем все записи
    for article in articles:
        db.session.delete(article)

    # Очищаем ячейку
    cell.part_name = None
    cell.article = None
    cell.quantity = 0

    db.session.commit()

    flash(f"🧹 Ячейка {cell_name} очищена. Удалено {articles_count} позиций ({total_removed} шт.)", "success")
    return redirect(url_for('grid'))


@app.route('/cell/<cell_name>')
def cell_detail(cell_name):
    """Детальная страница ячейки (что именно в ней хранится)"""
    cell = Cell.query.filter_by(name=cell_name).first_or_404()
    articles = Article.query.filter_by(cell=cell_name).all()
    return render_template('cell_detail.html', cell=cell, articles=articles, max_capacity=MAX_CAPACITY)


@app.route('/clear_all')
def clear_all():
    """Очистка всего склада (для тестирования)"""
    # Удаляем все запчасти
    Article.query.delete()
    # Очищаем все ячейки
    for cell in Cell.query.all():
        cell.part_name = None
        cell.article = None
        cell.quantity = 0
    db.session.commit()
    flash("🧹 Весь склад очищен!", "success")
    return redirect(url_for('index'))


if __name__ == '__main__':
    print("=" * 50)
    print("🚀 ЗАПУСК СИСТЕМЫ УПРАВЛЕНИЯ СКЛАДОМ")
    print("=" * 50)
    print(f"📦 Максимальная вместимость ячейки: {MAX_CAPACITY} шт.")
    print(f"🗺️  Ячейки склада: A1, A2, A3, B1, B2, B3, C1, C2, C3")
    print(f"🌐 Сервер запущен: http://127.0.0.1:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)