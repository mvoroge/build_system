import os
from os import path as os_path
from multiprocessing.pool import ThreadPool
import json
import subprocess
import shutil
from time import monotonic as time_now
from tempfile import TemporaryDirectory

from models import Job, Jobs

STATUSES = {
    0: "failure",
    1: "running",
    2: "success",
}


def run_job(current_job: Job, work_dir: str):
    """
    :param current_job: задача
    :param work_dir: временная рабочая директория
    :return: путь к полученному артефакту, если успешно, пустая строка, если при исполнении появилась ошибка
    """
    try:
        # Получение команд
        commands = current_job.commands
        timeout = current_job.timeout
        # Переход во временную папку
        for command in commands:
            p = subprocess.Popen(command, cwd=work_dir, shell=True)
            try:
                if timeout is None:
                    res = p.wait()
                else:
                    # В описании задачи указано, что timeout относится к задаче, поэтому после выполнения каждой команды
                    # общий timeout уменьшается на время его выполнения
                    start = time_now()
                    res = p.wait(timeout=timeout)
                    timeout -= time_now() - start

            except subprocess.TimeoutExpired as e:
                # Убийство основного и дочерних процессов в случае таймаута
                p.communicate()
                p.kill()
                return ''
            if res != 0:
                return ''
        else:
            # Предполагается, что для каждой задачи создаётся один артефакт
            new_artifact = os_path.join(work_dir, os.listdir(work_dir)[0])
            return new_artifact
    except Exception as e:
        print(f'Во время попутки выполнить задачу, возникла непредвиденная ошибка!\n{e}')
        return ''


def parse_config(cnf_path: str):
    try:
        # Чтение файла конфигурации
        with open(cnf_path) as f:
            cnf_data = json.load(f)

        return cnf_data["jobs"], cnf_data["goals"]

    except FileNotFoundError as e:
        assert False, 'Ошибка доступа к файлу конфигурации!'

    except KeyError as e:
        assert False, 'Формат файла конфигурации не соответствует требованиям!'

    except Exception as e:
        assert False, f'Ошибка при чтении файла конфигурации!\n{e}'


if __name__ == '__main__':
    # Создание папки с артефактами в случае его отсутствия
    if not os_path.exists('artifacts'):
        os.mkdir('artifacts')
    ARTIFACTS_DIR = os_path.abspath('artifacts')

    from sys import argv
    # config_path = abspath(argv[1])
    config_path = os_path.abspath('test_cnfg.json')
    assert os_path.isfile(config_path), 'Путь недействительный!'

    jobs = Jobs(*parse_config(cnf_path=config_path))

    result = {
        "state": "success",
        "jobs": [],
    }

    set_ready_job = set()   # Множество готовых задач
    tmp_wrk_dirs = dict()   # Словарь с рабочими директориями задач
    while True:
        # Определение пула задач, которые можно запустить параллельно
        if len(jobs.run_queue) == 1:
            parallel_run = list(jobs.run_queue)
        else:
            parallel_run = []
            for job_name in jobs.run_queue:
                # Если все зависимые задачи выполнены
                if not set(jobs[job_name].depends_on) - set_ready_job:
                    parallel_run.append(job_name)
                if len(parallel_run) == 3:
                    break

        # Создаём временные директории для каждой из задач
        tmp_wrk_dirs |= {job_name: TemporaryDirectory() for job_name in parallel_run}  # используется "|" (python 3.9+)
        """
            Из-за того, что основное действие исполнения задач - ожидание выполнения процессов - нет необходимости 
            использовать multiprocessing (команды же и так исполняются в отдельных процессах).
            Количество потоков зависит от количества возможных к параллельному исполнению  
        """
        with ThreadPool(len(parallel_run)) as p:
            res_runs = list(p.starmap(run_job, iterable=[(jobs[name], tmp_wrk_dirs[name].name) for name in parallel_run]))

        for i in range(len(parallel_run)):
            result_job = {
                "name": parallel_run[i],
                "state": "success" if res_runs[i] else "failure",
            }

            # Копирование артефакта в папку артефактов, если задача - цель сборки
            if parallel_run[i] in jobs.goals and res_runs[i]:
                artifact_path = os_path.join(ARTIFACTS_DIR, parallel_run[i])
                # Если артефакт с таким именем уже существует, то он удаляется
                if os_path.exists(artifact_path):
                    os.remove(artifact_path)
                shutil.copy(res_runs[i], ARTIFACTS_DIR)
                result_job["artifact"] = artifact_path

            # Добавление выполнения задачи в результирующий массив
            result["jobs"].append(result_job)

            # Копирование артефактов зависимых задач в рабочую директорию родительской
            """
            Данное действие безопасно, так как одновременно не могут быть выполнены зависимые друг от друга
            задачи, так же все зависимые задачи были выполнены на предыдущих шагах итерации, то есть
            их артефакты уже есть
            """
            if jobs[parallel_run[i]].depends_on is not None and res_runs[i]:
                inp_dir = os_path.join(tmp_wrk_dirs[parallel_run[i]].name, 'input')
                os.mkdir(inp_dir)
                for dep in jobs[parallel_run[i]].depends_on:
                    shutil.copy(os_path.join(tmp_wrk_dirs[dep].name, dep), inp_dir)

        # Обновление информации об уже проверенных задачах
        jobs.run_queue -= set(parallel_run)

        # Удаление ранее временных рабочих папок, если все задачи проверены или одна из задач закончилась неуспешно
        if not jobs.run_queue or '' in res_runs:
            map(lambda name: tmp_wrk_dirs[name].clenup(), tmp_wrk_dirs.keys())
            if '' in res_runs:
                result["state"] = "failure"
                for job_name in jobs.run_queue:
                    result["jobs"].append(
                        {
                            "name": job_name,
                            "state": "failure",
                        }
                    )
            break

    # Вывод результата сборки
    print(json.dumps(result, indent=3))
