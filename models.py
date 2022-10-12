from typing import Optional
from pydantic import BaseModel


# Класс Job соответствует структуре задачи
class Job(BaseModel):
    name: str
    commands: list
    depends_on: Optional[list] = []
    timeout: Optional[int] = None


# Для удобства вся информации хранится в классе Jobs
class Jobs:
    def __init__(self, jobs: list, goals: list):
        self.goals = goals                                          # Цели сборки
        self.jobs_dict = {job['name']: Job(**job) for job in jobs}  # Словарь всех задач (имя задачи: объект класса Job)
        self.names = list(self.jobs_dict.keys())                    # Список названий задач
        self.run_queue = set(self.names)                            # Множество имен задач, которые ещё не были проверены

    def __getitem__(self, key):
        return self.jobs_dict[key]

    def __len__(self):
        return len(self.jobs_dict)

    # Данный способ организации очереди подходит для последовательного выполнения задач,
    # при этом такая очередь подошла бы даже для зависимостей, которые можно представить в виде
    # направленного ориентированного графа (необязательно ациклический)
    # def _rec_init_run_queue(self, current_job_name):
    #     if current_job_name not in self.run_queue:
    #         past = self.jobs_dict[current_job_name].depends_on
    #         if len(past):
    #             for job_name in past:
    #                 if job_name not in self.run_queue:
    #                     self._rec_init_run_queue(job_name)
    #             self.run_queue.append(current_job_name)
    #         else:
    #             self.run_queue.insert(0, current_job_name)
