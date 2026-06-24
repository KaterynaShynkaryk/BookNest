# 📚 BookNest

Персональний менеджер цифрової бібліотеки, створений на **Python, Django, Django Templates, Bootstrap, HTML/CSS** з конфігурацією, готовою до деплою на **Render + PostgreSQL**.

<p align="center">
  <a href="https://booknest-j0pb.onrender.com">
    <img src="https://img.shields.io/badge/▶%20Live%20Demo-BookNest-6f8fa6?style=for-the-badge" alt="Live Demo">
  </a>
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Django-Web%20App-0c4b33?style=for-the-badge&logo=django" alt="Django">
  <img src="https://img.shields.io/badge/Deploy-Render-46e3b7?style=for-the-badge&logo=render" alt="Render">
</p>

<p align="center">
  <a href="README.md">English README</a> ·
  <a href="#демо">Демо</a> ·
  <a href="#технічні-рішення">Технічні рішення</a> ·
  <a href="#запуск-локально">Запуск</a> ·
  <a href="#тести-та-якість">Тести</a>
</p>

---

## Про проєкт

**BookNest** — це вебзастосунок для ведення персональної цифрової бібліотеки. Користувач може додавати книги, відстежувати прогрес читання, створювати полички, писати нотатки, позначати важливе та переглядати статистику прочитаного.

Проєкт розроблений як портфоліо-застосунок, що демонструє повний цикл створення Django-застосунку: моделі даних, CRUD-логіку, авторизацію, фільтри, валідацію форм, адаптивні шаблони, автоматизовані тести та конфігурацію деплою.

## Демо

➡️ **[Відкрити BookNest](https://booknest-j0pb.onrender.com)**

### Дані для демо-входу

Для перегляду деплой-версії можна використати демоакаунт:

```text
Username: demo
Password: demo12345
```

---

![Бібліотека](docs/screenshots/01_library.png)

---

## Технології

| Напрям | Технології |
|---|---|
| Backend | Python 3.12+, Django |
| Frontend | Django Templates, Bootstrap, HTML5, custom CSS |
| База даних | SQLite локально, PostgreSQL-ready для деплою |
| Авторизація | Django authentication views та ізоляція даних користувачів |
| Зовнішні дані | Пошук книг через зовнішнє books API |
| Деплой | Render-конфігурація через `render.yaml` |
| Тести | Django `TestCase` suite для основних сценаріїв застосунку |

---

## Основні можливості

### Бібліотека книг

![Деталі книги](docs/screenshots/02_book_detail.png)

- додавання книг вручну або через зовнішній пошук;
- збереження назви, автора, жанру, видавництва, серії, опису та обкладинки;
- статуси читання: **Бажанка**, **Заплановано**, **Читаю**, **Прочитано**, **Закинуто**;
- оцінювання прочитаних книг;
- позначення книг як улюблених;
- пошук і фільтрація за статусом, жанром, видавництвом та улюбленими.

![Фільтри](docs/screenshots/08_filters.png)

### Полички

![Полички](docs/screenshots/03_shelves.png)

- створення власних поличок;
- керування книгами всередині полички;
- автоматичні полички для книжкових серій;
- прев’ю полички з двома рядами обкладинок;
- фільтри всередині кожної полички.

### Нотатки

![Нотатки](docs/screenshots/04_notes.png)

- загальні нотатки;
- нотатки до конкретної книги;
- номер сторінки для цитат або важливих фрагментів;
- редагування та видалення нотаток;
- улюблені нотатки підіймаються вище у списку.

### Статистика

![Статистика](docs/screenshots/05_statistics.png)

- загальна кількість книг;
- кількість прочитаних книг;
- кількість книг у процесі читання;
- кількість книг у бажанках;
- автоматичні списки прочитаних книг за роками;
- згортання та розгортання списків за роками.

### Акаунт

![Вхід](docs/screenshots/06_login.png)

- реєстрація користувача;
- вхід і вихід з акаунта;
- приватність книг, поличок і нотаток кожного користувача;
- відновлення пароля через електронну пошту.

![Відновлення паролю](docs/screenshots/07_reset_password.png)

### Адаптація під телефон

<p align="center">
  <img src="docs/screenshots/09_mobi_library.jpg" alt="Бібліотека на телефоні" width="220">
  <img src="docs/screenshots/10_mobi_detail.jpg" alt="Деталі книги на телефоні" width="220">
  <img src="docs/screenshots/11_mobi_shelves.jpg" alt="Полички на телефоні" width="220">
  <img src="docs/screenshots/12_mobi_statistics.jpg" alt="Статистика на телефоні" width="220">
</p>

- інтерфейс адаптується під мобільні екрани;
- навігація, картки книг, полички, форми та фільтри зручно перебудовуються для меншої ширини;
- сторінки можна використовувати як з комп’ютера, так і зі смартфона.

---

## Технічні рішення

- **Ізоляція даних користувачів:** книги, полички, нотатки та статистика прив’язані до авторизованого користувача.
- **CRUD-сценарії:** книги, полички та нотатки можна створювати, переглядати, редагувати, фільтрувати й видаляти через Django views та forms.
- **Автоматичні полички серій:** якщо книги належать до серії, BookNest може синхронізувати автоматичні серійні полички з бібліотекою користувача.
- **Валідація форм:** статуси читання, дати, рейтинги, полички та користувацькі варіанти перевіряються на сервері.
- **Пошук і фільтри:** списки підтримують фільтрацію за статусом, жанром, видавництвом, улюбленими та текстовий пошук.
- **Перевикористання шаблонів:** Django templates допомагають зберігати консистентність UI на різних сторінках.
- **Адаптивний інтерфейс:** custom CSS і Bootstrap-утиліти підтримують desktop і mobile layout.
- **Готовність до деплою:** у проєкті є Render-конфігурація та структура для production database settings.

---

## Архітектура

```text
BookNest/
├── backend/                 # налаштування Django-проєкту, URL routing, WSGI/ASGI entry points
├── library/                 # основний Django-застосунок
│   ├── models.py            # книги, полички, нотатки та зв’язки між ними
│   ├── views.py             # сторінки, фільтрація та бізнес-сценарії
│   ├── forms.py             # форми книг, прогресу, нотаток і поличок з валідацією
│   ├── series_shelves.py    # helpers для автоматичних поличок книжкових серій
│   ├── templates/library/   # UI templates застосунку
│   └── tests.py             # Django-тести для ключових сценаріїв і валідації
├── templates/registration/  # авторизація та відновлення пароля
├── static/css/              # custom responsive styles
├── docs/screenshots/        # скріншоти README для desktop і mobile views
├── render.yaml              # Render deployment configuration
├── requirements.txt         # Python dependencies
└── manage.py                # Django command-line entry point
```

Проєкт має класичну Django-структуру: `backend` містить налаштування рівня проєкту, а `library` — доменну логіку книг, поличок, нотаток, фільтрів, форм, шаблонів і тестів. Шаблони авторизації винесені в `templates/registration`, стилі — у `static/css`, а деплой описаний через `render.yaml`.

---

## Запуск локально

```bash
git clone <repository-url>
cd BookNest
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_user  # optional: creates demo / demo12345
python manage.py runserver
```

Локальна адреса:

```text
http://127.0.0.1:8000/
```

---

## Тести та якість

Запуск Django-тестів і системних перевірок:

```bash
python manage.py test
python manage.py check
```

Поточне тестове покриття представлено Django test suite у `library/tests.py`. Тести покривають основні сценарії: авторизацію, керування книгами, полички, автоматичні серійні полички, нотатки, фільтри, форми, перевірку власника даних і правила валідації. Числовий coverage report ще не налаштований; хорошим наступним кроком буде додати `coverage.py` або CI coverage reporting.

---

## Подальший розвиток

- графіки статистики;
- цілі читання на рік;
- експорт бібліотеки у CSV/PDF;
- публічний профіль читача;
- темна тема;
- покращений імпорт книг із зовнішніх джерел;
- числовий coverage report у CI.