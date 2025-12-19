# Blockchain Medical Project

## Описание

Проект демонстрирует взаимодействие участников медицинской системы  (пациент, больница, регулятор) с использованием **Hyperledger Indy** и агентной архитектуры. В качестве тестового блокчейна используется репозиторий **von-network**.

---

### Общие требования
- Python 3.8+
- Docker
- Docker Compose
- pip

---

# Запуск на Windows

> ⚠️ Рекомендуется использовать **Docker Desktop с WSL2**  
> Запуск команд выполняется из **Git Bash** или терминала WSL.


## Структура проекта
-   `requirements.txt`: Список зависимостей.


# Запуск на Windows

1. Склонируйте основной репозиторий: `git clone https://github.com/MelikovMan/blockchain-project.git`
2. Склонируйте репозиторий: `git clone https://github.com/bcgov/von-network`
3. Перейдите в директорию и начните сборку: `cd von-network & ./manage build `
4. Выполните запуск: `./manage start`
5. В разных терминалах выполните команды по запуску агентов:

```bash
docker-compose -f hospital-docker-compose.yml up -d
docker-compose -f patient-docker-compose.yml up -d
docker-compose -f regulator-docker-compose.yml up -d
```
>⚠️ Важно: после выполнения перейдите в `http://localhost:9000/` и вставьте в поле "Wallet seed" `very_strong_hospital_seed0000000` и `state_regulator_seed_000000001`. Нажмите `Register DID`.
6. Установите необходимые зависимости:
```
pip install --upgrade pip
pip install -r requirements.txt
```
7. Также в разных терминалах запустите контроллеры (последовательность важна):
```
# python init_controller.py
# python regular_controller/main.py
python hospital_controller/main.py
python patient_controller.py
```
Последовательность тестирования:
Откройте интерфейс пациента - http://localhost:8060; Запустите сценарий взаимодействия - `python medical_scenario.py`; Наблюдайте за логами в обоих контроллерах


# Запуск на Linux
Необходимо установить docker и docker compose - [ссылка](https://ruvds.com/ru/helpcenter/kak-ustanovit-docker-i-docker-compose/)

1. Склонируйте основной репозиторий: `git clone https://github.com/MelikovMan/blockchain-project.git`
2. Склонируйте репозиторий: `git clone https://github.com/bcgov/von-network`
3. Перейдите в директорию и начните сборку: `cd von-network & ./manage build `
4. Выполните запуск: `./manage start`
5. В `hospital-docker-compose.yml`, `patient-docker-compose.yml` и `regulator-docker-compose.yml` замените все вхождения `host.docker.internal` на `172.17.0.1 `
6. В разных терминалах выполните команды по запуску агентов:
```
docker compose -f hospital-docker-compose.yml up -d
docker compose -f patient-docker-compose.yml up -d
docker compose -f regulator-docker-compose.yml up -d
```
>⚠️ Важно: после выполнения перейдите в `http://localhost:9000/` и вставьте в поле "Wallet seed" `very_strong_hospital_seed0000000` и `state_regulator_seed_000000001`. Нажмите `Register DID`.
7. Установите необходимые зависимости:
```
pip install --upgrade pip
pip install -r requirements.txt
```
8. Также в разных терминалах запустите контроллеры (последовательность важна):
```
python3 hospital/hospital_controller.py
python3 patient_controller.py
```

- Интерфейс пациента: http://localhost:8060
- Swagger UI: http://localhost:8031