import psycopg2
from regulator_controller.internal.domain.config import RegulatorRepo as ConfigRegulatorRepo


class RegulatorRepo:
    def __init__(self, config: ConfigRegulatorRepo):
        self.config = config
        self.connection = None
        self.cursor = None

        self.connect()

    def connect(self):
        self.connection = psycopg2.connect(
            host=self.config.Host,
            port=self.config.Port,
            database=self.config.Name,
            user=self.config.User,
            password=self.config.Password,
        )
        if self.connection:
            self.cursor = self.connection.cursor()

    def close_connection(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def execute_and_fetch(self, sql, params=None):
        if self.connection:
            self.cursor.execute(sql, params)
            self.connection.commit()
            result = self.cursor.fetchall()

            columns = [col[0] for col in self.cursor.description]
            return [dict(zip(columns, row)) for row in result], True

        return None, False

    def execute(self, sql, params):
        if self.connection:
            self.cursor.execute(sql, params)
            self.connection.commit()

            return True

        return False
