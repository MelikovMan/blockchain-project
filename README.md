Подготовка инфраструктуры:

```bash
# Запуск тестового блокчейна Indy
cd von-network
./manage start

# В разных терминалах запускаем агентов
docker-compose -f docker-compose.hospital.yml up
docker-compose -f docker-compose.patient.yml up

# Запускаем контроллеры
python hospital_controller.py
python patient_controller.py
```
Последовательность тестирования:

Откройте интерфейс пациента: http://localhost:8060

Запустите сценарий взаимодействия: python medical_scenario.py

Наблюдайте за логами в обоих контроллерах