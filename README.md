# ToDo API

Учебный REST API для управления задачами, разработанный на **Python** с использованием **FastAPI**.

Проект позволяет просматривать, искать, создавать, обновлять и удалять задачи. Задачи хранятся в памяти и сбрасываются при перезапуске приложения.

### Технологии
- Python
- FastAPI
- Uvicorn

### Запуск проекта

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Документация API доступна по адресам `http://127.0.0.1:8000/docs` и `http://127.0.0.1:8000/redoc`.

### Основные эндпоинты

| Метод | Маршрут | Описание |
|---|---|---|
| GET | `/` | Информация об API |
| GET | `/api/v1/tasks` | Все задачи |
| POST | `/api/v1/tasks` | Создать задачу |
| GET | `/api/v1/tasks/{task_id}` | Задача по ID |
| PUT | `/api/v1/tasks/{task_id}` | Обновить задачу |
| PATCH | `/api/v1/tasks/{task_id}/complete` | Отметить задачу выполненной |
| DELETE | `/api/v1/tasks/{task_id}` | Удалить задачу |
| GET | `/api/v1/stats` | Статистика задач |
| GET | `/api/v1/tasks/search?q=...` | Поиск задач |
| GET | `/api/v1/tasks/status/{status}` | Фильтрация по статусу |
| GET | `/api/v1/tasks/quadrant/{quadrant}` | Фильтрация по квадранту |

Для создания задачи передайте `title` (3–100 символов), `is_important` и `is_urgent`. Поле `description` необязательно. Неизвестные поля отклоняются с кодом 422.

Проверка API: `python -m unittest discover -s tests -v`.
