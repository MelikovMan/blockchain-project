Подготовка инфраструктуры:

```bash
# Запуск тестового блокчейна Indy
git clone https://github.com/bcgov/von-network
cd von-network
./manage build (один раз)
./manage start

# В разных терминалах запускаем агентов
docker-compose -f hospital-docker-compose.yml up -d
docker-compose -f patient-docker-compose.yml up -d
docker-compose -f regulator-docker-compose.yml up -d

# Запускаем контроллеры
# python init_controller.py
# python regular_controller.py
python hospital_controller.py
python patient_controller.py
```
Последовательность тестирования:

Откройте интерфейс пациента: http://localhost:8060

Запустите сценарий взаимодействия: python medical_scenario.py

Наблюдайте за логами в обоих контроллерах