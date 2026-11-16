# ToDo API

Учебный REST API для управления задачами, разработанный на **Python** с использованием **FastAPI**.

Проект позволяет просматривать, искать и создавать задачи. Задачи хранятся в памяти и сбрасываются при перезапуске приложения.

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
| GET | `/tasks` | Все задачи |
| POST | `/tasks` | Создать задачу |
| GET | `/tasks/{task_id}` | Задача по ID |
| GET | `/tasks/stats` | Статистика задач |
| GET | `/tasks/search?q=...` | Поиск задач |
| GET | `/tasks/status/{status}` | Фильтрация по статусу |
| GET | `/tasks/quadrant/{quadrant}` | Фильтрация по квадранту |

Для создания задачи передайте `title`, `is_important` и `is_urgent`. Поле `description` необязательно.
