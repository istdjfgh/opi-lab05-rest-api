"""Запускає колекцію postman_collection.json через newman (консольний «двійник» Postman).

Запуск: python scripts/run_newman.py [шлях_до_newman]
1. Створює тимчасову БД і заповнює її тестовими даними (seed_data) — робоча db.sqlite не змінюється.
2. Піднімає API на вільному порту в окремому потоці.
3. Виконує колекцію; звіти — у lab-reports/newman/ (report.html, report.json, cli.txt).
Потрібен Node.js і newman: npm install -g newman newman-reporter-htmlextra
"""
import os
import shutil
import subprocess
import sys
import tempfile
import threading

from werkzeug.serving import make_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import seed_data  # noqa: E402
from app import create_app  # noqa: E402

REPORTS = os.path.join(ROOT, 'lab-reports', 'newman')
API_KEY = 'newman-key'


def main():
    newman = sys.argv[1] if len(sys.argv) > 1 else shutil.which('newman')
    if not newman:
        sys.exit('newman не знайдено: npm install -g newman newman-reporter-htmlextra')
    os.makedirs(REPORTS, exist_ok=True)

    app = create_app({'DATABASE': os.path.join(tempfile.mkdtemp(), 'newman.sqlite'), 'API_KEY': API_KEY})
    with app.app_context():
        seed_data.seed()
    server = make_server('127.0.0.1', 0, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    command = [
        newman, 'run', os.path.join(ROOT, 'postman_collection.json'),
        '--env-var', f'baseUrl=http://127.0.0.1:{server.server_port}',
        '--env-var', f'apiKey={API_KEY}',
        '--reporters', 'cli,htmlextra,json',
        '--reporter-htmlextra-export', os.path.join(REPORTS, 'report.html'),
        '--reporter-htmlextra-title', 'Кубик — результати тестування REST API',
        '--reporter-htmlextra-browserTitle', 'Newman: Кубик API',
        '--reporter-json-export', os.path.join(REPORTS, 'report.json'),
        '--color', 'off',
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    with open(os.path.join(REPORTS, 'cli.txt'), 'w', encoding='utf-8') as file:
        file.write(result.stdout)
    print(result.stdout[-3000:])
    server.shutdown()
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
