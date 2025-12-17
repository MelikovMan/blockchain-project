Подготовка инфраструктуры:

```bash
# Запуск тестового блокчейна Indy - нужен Docker
git clone https://github.com/bcgov/von-network
cd von-network
./manage build (один раз)
./manage start
cd ..
# В разных терминалах запускаем агентов На MacOS и Windows в compose файлах используется host.docker.internal в конфигурациях. Для linux - надо заменить на результат команды
#docker network inspect bridge -f '{{range .IPAM.Config}}{{.Gateway}}{{end}}'
docker-compose -f hospital-docker-compose.yml up -d
docker-compose -f patient-docker-compose.yml up -d
docker-compose -f regulator-docker-compose.yml up -d

# Запускаем контроллеры - на python, нужен Flask и requests. Можно установить через venv
# python init_controller.py
# python regular_controller.py
python hospital_controller.py
python patient_controller.py
```
Последовательность тестирования:

Откройте интерфейс пациента: http://localhost:8060

Запустите сценарий взаимодействия: python medical_scenario.py

Наблюдайте за логами в обоих контроллерах