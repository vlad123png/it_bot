import asyncio
import json
import subprocess


async def get_audio_duration(file_path: str) -> float:
    """
    Получает продолжительность аудио файла через FFmpeg
    :param file_path: Путь к аудио файлу
    :return: Продолжительность в секундах
    """
    command = [
        'ffprobe',
        '-i', file_path,
        '-show_entries', 'format=duration',
        '-v', 'quiet',
        '-of', 'json'
    ]

    try:
        result = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            raise RuntimeError(f'Ошибка FFmpeg: {stderr.decode()}')

        info = json.loads(stdout.decode())
        duration = float(info['format']['duration'])
        return duration
    except Exception as e:
        raise RuntimeError(f'Не удалось получить длительность файла: {e}')