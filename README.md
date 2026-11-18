# speedtest — Download Speed Measurement CLI

[![Tests](https://img.shields.io/badge/tests-62%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![Type Checked](https://img.shields.io/badge/mypy-strict%20clean-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

> **Language / Язык:** [English](#english) | [Русский](#русский)

---

<a name="english"></a>
## English

A modern Python CLI tool that measures internet download speed with detailed per-phase timing breakdown (DNS resolution, TCP connect, TLS handshake, TTFB, and content transfer).

### Why Two Modes?

All VPN traffic runs over HTTPS. Understanding the difference between **connection setup overhead** and **raw channel throughput** is critical for VPN performance analysis:

- **Fresh mode** (`--mode fresh`): Each request opens a new TCP/TLS connection. Measures real user experience, including DNS lookup, TCP handshake, and TLS negotiation overhead.
- **Reuse mode** (`--mode reuse`): All requests share a single persistent connection. Measures raw channel throughput without connection setup costs.
- **Both mode** (`--mode both`, default): Runs both sequentially and displays a side-by-side comparison table with connection overhead analysis.

### Quick Start

#### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

#### Installation

```bash
git clone https://github.com/aqwarius2003/speedtest.git
cd speedtest
uv sync
```

Or with standard `pip`:

```bash
pip install -e .
```

#### Usage

```bash
# Default: 10 requests in both modes with comparison table
uv run speedtest https://example.com/large-file.jpg

# Custom request count
uv run speedtest https://example.com/file.bin -n 20

# Single mode
uv run speedtest https://example.com/file.bin --mode fresh
uv run speedtest https://example.com/file.bin --mode reuse

# Verbose: show per-request timing breakdown
uv run speedtest https://example.com/file.bin -n 5 -v

# Custom timeout
uv run speedtest https://example.com/file.bin -t 60

# Skip reachability pre-validation check
uv run speedtest https://example.com/file.bin --skip-validation
```

*(You can also use `uv run python -m speedtest <URL>`)*

#### Recommended Test Targets

Verified, high-bandwidth HTTPS endpoints ideal for benchmarking without rate-limiting:

- **Cloudflare Speed Test CDN (10 MB payload, recommended):**
  ```bash
  uv run speedtest "https://speed.cloudflare.com/__down?bytes=10000000" -n 10
  ```
- **High-Resolution Photo (Unsplash CDN, ~6.2 MB):**
  ```bash
  uv run speedtest "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=100&w=4800&auto=format&fit=crop" -n 5
  ```
- **Heavy Astronomy Panorama (Wikimedia Commons / ESO, 51.2 MB):**
  ```bash
  uv run speedtest "https://upload.wikimedia.org/wikipedia/commons/e/ea/Carina_Nebula.jpg" -n 2 -t 60
  ```

### Example Output

```text
Target: https://example.com/large-image.jpg
Requests: 10 per mode
Timeout: 30s

Validating URL... ✓ URL reachable (HTTP 200)

Running fresh connection mode...
━━━━━━━━━━━━━━━━━━━━ 100% Fresh

Running reuse connection mode...
━━━━━━━━━━━━━━━━━━━━ 100% Reuse

                  Connection Mode Comparison
┌──────────────────────┬─────────────────┬─────────────────┐
│ Metric               │           Fresh │           Reuse │
├──────────────────────┼─────────────────┼─────────────────┤
│ Avg DNS              │        42.15 ms │         0.00 ms │
│ Avg TCP Connect      │        25.30 ms │         0.00 ms │
│ Avg TLS Handshake    │        68.47 ms │         0.00 ms │
│ Avg TTFB             │        15.22 ms │         8.44 ms │
│ Avg Transfer         │       320.10 ms │       310.50 ms │
├──────────────────────┼─────────────────┼─────────────────┤
│ Avg Speed            │       12.40 MB/s│       14.10 MB/s│
│ Min Speed            │       10.80 MB/s│       13.20 MB/s│
│ Max Speed            │       14.20 MB/s│       15.00 MB/s│
│ Std Dev              │        1.20 MB/s│        0.60 MB/s│
├──────────────────────┼─────────────────┼─────────────────┤
│ Total Downloaded     │        40.00 MB │        40.00 MB │
│ Requests             │           10/10 │           10/10 │
└──────────────────────┴─────────────────┴─────────────────┘

╭─────────────── Connection Setup Overhead Analysis ──────────────╮
│ Connection setup overhead (DNS + TCP + TLS): 28.8% of total     │
│ request time in fresh mode.                                     │
│ Connection reuse saves 135.9 ms per request.                    │
│ Reuse mode is 13.7% faster than fresh connections.              │
╰─────────────────────────────────────────────────────────────────╯
```

### Architecture

```text
speedtest/
├── __init__.py        # Package metadata
├── __main__.py        # Entry point: python -m speedtest
├── cli.py             # Typer CLI with Rich progress bars
├── measure.py         # curl_cffi low-level measurement engine
├── models.py          # Frozen dataclasses (TimingBreakdown, RequestResult, SessionStats)
├── stats.py           # Statistical computations (mean, std, comparison)
├── display.py         # Rich table formatting and overhead panel
tests/
├── test_models.py     # Unit tests for data models
├── test_measure.py    # Unit & integration tests for measurement engine
├── test_stats.py      # Unit tests for statistics
├── test_display.py    # Unit tests for Rich formatters and tables
├── test_cli.py        # CLI tests using CliRunner
```

### Design Decisions

#### Why `curl_cffi` instead of `requests`, `httpx`, or `aiohttp`?

Standard Python HTTP clients (**`requests`**, **`httpx`**, and **`aiohttp`**) **do not expose per-phase timing breakdown** out of the box:
- They only provide total elapsed round-trip time (`response.elapsed` or total request duration).
- None of them provide native programmatic access to the individual milestones of connection establishment: DNS resolution time, TCP handshake duration, and TLS negotiation time.
- Attempting to extract these phases in those libraries requires fragile monkeypatching of low-level transport adapters, parsing internal debug logs, or intercepting socket hooks. This approach is brittle and unsuitable for professional network telemetry.

**Why `curl_cffi` was chosen:**
- Direct access to **libcurl's native `getinfo()` metrics**: `NAMELOOKUP_TIME`, `CONNECT_TIME`, `APPCONNECT_TIME`, `STARTTRANSFER_TIME`, and `TOTAL_TIME`. These are the exact industry-standard timers used by `curl -w` and professional network diagnostic tools.
- **Pre-compiled wheels** for Windows, macOS, and Linux (unlike `pycurl`, which requires local C compilation and libcurl development headers, causing installation friction).
- True, verifiable socket and connection reuse across requests on the same `Curl` handle.

#### Why not raw sockets?

Implementing manual socket timing via `socket.getaddrinfo()` -> `socket.create_connection()` -> `ssl.wrap_socket()` provides raw control but significantly inflates codebase complexity, exposes the tool to TLS cipher/SNI negotiation bugs, and requires hand-rolled HTTP state machines and redirect handling. `curl_cffi` offers identical microsecond precision with battle-tested reliability.

#### Speed Units

All speeds are reported in **decimal units**: **1 MB/s = 1,000,000 bytes/second** (rather than binary $1\text{ MiB} = 1{,}048{,}576\text{ B}$). This matches network engineering, ISP throughput benchmarks, and telecommunications standards.

#### Statistical Methodology

- **Population standard deviation** ($\sqrt{\frac{1}{N} \sum (x - \mu)^2}$) is used because the measurements represent the entirety of the controlled trials executed, rather than an inferred sample of an unobserved population.
- Failed requests (e.g. timeouts or 4xx/5xx HTTP errors) are excluded from speed and timing averages so they do not artificially distort metrics, but they are clearly reported in total and failure counters.

### Running Tests

```bash
# Offline unit tests only (fast, runs without network access)
uv run pytest -m "not integration" -v

# Full test suite (includes live network integration tests)
uv run pytest -v

# Static type checking
uv run mypy speedtest tests
```

### Future Improvements

- JSON and CSV output formats for automated CI/CD and monitoring pipelines.
- `--compare` flag: persist baseline benchmark results to file and compare before/after VPN activation.
- HTTP/2 vs HTTP/1.1 vs HTTP/3 (QUIC) protocol performance comparison.
- Upload speed measurement support via chunked HTTP PUT/POST streaming.
- Percentile latency calculations ($p_{50}$, $p_{90}$, $p_{99}$).

---

<a name="русский"></a>
## Русский

Современная консольная утилита (CLI) на Python для замера скорости загрузки данных из интернета с детальным покомпонентным анализом времени (разрешение DNS, установка TCP-соединения, TLS-рукопожатие, TTFB и передача полезных данных).

### Зачем два режима?

Весь пользовательский трафик в современных VPN передается поверх HTTPS. Для объективной оценки производительности VPN-канала принципиально важно разделять **затраты на установку соединения** и **чистую пропускную способность канала**:

- **Режим Fresh** (`--mode fresh`): каждый запрос выполняется в рамках нового TCP/TLS-соединения. Показывает реальный пользовательский опыт (открытие страниц "с нуля"), включая накладные расходы на DNS, TCP и TLS.
- **Режим Reuse** (`--mode reuse`): все запросы передаются через одно постоянное соединение (keep-alive). Измеряет максимальную чистую скорость канала без задержек на рукопожатия.
- **Режим Both** (`--mode both`, по умолчанию): последовательно выполняет оба сценария и выводит наглядную сравнительную таблицу с детальным анализом оверхеда на установку соединения.

### Быстрый старт

#### Требования
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (рекомендуется) или pip

#### Установка

```bash
git clone https://github.com/aqwarius2003/speedtest.git
cd speedtest
uv sync
```

Либо через стандартный `pip`:

```bash
pip install -e .
```

#### Примеры использования

```bash
# По умолчанию: 10 запросов в обоих режимах с таблицей сравнения
uv run speedtest https://example.com/large-file.jpg

# Указать своё количество запросов
uv run speedtest https://example.com/file.bin -n 20

# Запуск только одного режима
uv run speedtest https://example.com/file.bin --mode fresh
uv run speedtest https://example.com/file.bin --mode reuse

# Подробный вывод по каждому запросу (verbose)
uv run speedtest https://example.com/file.bin -n 5 -v

# Настройка тайм-аута (в секундах)
uv run speedtest https://example.com/file.bin -t 60

# Пропустить предварительную проверку доступности URL
uv run speedtest https://example.com/file.bin --skip-validation
```

*(Также поддерживается запуск через `uv run python -m speedtest <URL>`)*

#### Рекомендуемые тестовые URL

Проверенные и стабильные HTTPS-эндпоинты, подходящие для бенчмарка без риска блокировок хостинга:

- **Cloudflare Speed Test CDN (10 МБ, рекомендуется):**
  ```bash
  uv run speedtest "https://speed.cloudflare.com/__down?bytes=10000000" -n 10
  ```
- **Фото в высоком разрешении (Unsplash CDN, ~6.2 МБ):**
  ```bash
  uv run speedtest "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=100&w=4800&auto=format&fit=crop" -n 5
  ```
- **Тяжелая астрономическая панорама (Wikimedia Commons / ESO, 51.2 МБ):**
  ```bash
  uv run speedtest "https://upload.wikimedia.org/wikipedia/commons/e/ea/Carina_Nebula.jpg" -n 2 -t 60
  ```

### Пример вывода в консоль

```text
Target: https://example.com/large-image.jpg
Requests: 10 per mode
Timeout: 30s

Validating URL... ✓ URL reachable (HTTP 200)

Running fresh connection mode...
━━━━━━━━━━━━━━━━━━━━ 100% Fresh

Running reuse connection mode...
━━━━━━━━━━━━━━━━━━━━ 100% Reuse

                  Connection Mode Comparison
┌──────────────────────┬─────────────────┬─────────────────┐
│ Metric               │           Fresh │           Reuse │
├──────────────────────┼─────────────────┼─────────────────┤
│ Avg DNS              │        42.15 ms │         0.00 ms │
│ Avg TCP Connect      │        25.30 ms │         0.00 ms │
│ Avg TLS Handshake    │        68.47 ms │         0.00 ms │
│ Avg TTFB             │        15.22 ms │         8.44 ms │
│ Avg Transfer         │       320.10 ms │       310.50 ms │
├──────────────────────┼─────────────────┼─────────────────┤
│ Avg Speed            │       12.40 MB/s│       14.10 MB/s│
│ Min Speed            │       10.80 MB/s│       13.20 MB/s│
│ Max Speed            │       14.20 MB/s│       15.00 MB/s│
│ Std Dev              │        1.20 MB/s│        0.60 MB/s│
├──────────────────────┼─────────────────┼─────────────────┤
│ Total Downloaded     │        40.00 MB │        40.00 MB │
│ Requests             │           10/10 │           10/10 │
└──────────────────────┴─────────────────┴─────────────────┘

╭─────────────── Connection Setup Overhead Analysis ──────────────╮
│ Connection setup overhead (DNS + TCP + TLS): 28.8% of total     │
│ request time in fresh mode.                                     │
│ Connection reuse saves 135.9 ms per request.                    │
│ Reuse mode is 13.7% faster than fresh connections.              │
╰─────────────────────────────────────────────────────────────────╯
```

### Архитектура проекта

```text
speedtest/
├── __init__.py        # Метаданные пакета
├── __main__.py        # Точка входа для `python -m speedtest`
├── cli.py             # CLI на базе Typer с прогресс-барами Rich
├── measure.py         # Низкоуровневый движок измерений на curl_cffi
├── models.py          # Неизменяемые датаклассы (TimingBreakdown, RequestResult, SessionStats)
├── stats.py           # Статистический модуль (среднее, std dev, сравнение режимов)
├── display.py         # Форматирование таблиц Rich и панели анализа оверхеда
tests/
├── test_models.py     # Тесты моделей данных
├── test_measure.py    # Модульные и интеграционные тесты движка измерений
├── test_stats.py      # Тесты математических расчётов и статистики
├── test_display.py    # Тесты вывода и форматирования таблиц
├── test_cli.py        # Тесты командной строки с CliRunner
```

### Архитектурные решения

#### Почему `curl_cffi`, а не `requests`, `httpx` или `aiohttp`?

Популярные HTTP-библиотеки в экосистеме Python (**`requests`**, **`httpx`**, **`aiohttp`**) **не предоставляют детальной статистики по фазам соединения**:
- Они отдают только общее затраченное время на запрос (`response.elapsed` или общее время корутины).
- Ни одна из них не позволяет штатным образом получить раздельное время на: разрешение имени DNS, TCP-рукопожатие и TLS-согласование шифрования.
- Попытки вытащить эти метрики из `requests` или `httpx` требуют либо нестабильного манкипатчинга сокетов/транспортов, либо парсинга отладочных логов библиотеки `httpcore`. В реальных инженерных задачах диагностики сетей такой подход считается хрупким и ненадежным.

**Почему был выбран `curl_cffi`:**
- Прямой нативный доступ к **метрикам таймингов libcurl через `getinfo()`**: `NAMELOOKUP_TIME`, `CONNECT_TIME`, `APPCONNECT_TIME`, `STARTTRANSFER_TIME` и `TOTAL_TIME`. Это промышленный стандарт замеров, лежащий в основе утилиты `curl -w` и профессиональных систем мониторинга.
- Поставляется с готовыми предсобранными бинарными пакетами (wheels) под Windows, macOS и Linux (в отличие от `pycurl`, требующего для сборки системные заголовки C и компилятор).
- Реальное и проверяемое переиспользование соединений в рамках одного дескриптора `Curl`.

#### Почему не сырые сокеты (`socket` + `ssl`)?

Ручное управление сокетами через `socket.getaddrinfo()` -> `socket.create_connection()` -> `ssl.wrap_socket()` дает максимальный низкоуровневый контроль, но чрезмерно раздувает кодовую базу, усложняет корректную обработку редиректов, пулов соединений и согласования версий TLS/ALPN. `curl_cffi` обеспечивает эквивалентную микросекундную точность на базе самого проверенного сетевого стека в мире.

#### Единицы измерения скорости

Все значения скорости отображаются в **десятичных единицах**: **1 MB/s = 1 000 000 байт/сек** (а не в двоичных $1\text{ MiB} = 1\,048\,576\text{ байт}$). Это строго соответствует стандартам телекоммуникационной индустрии, провайдеров связи и сетевой инженерии.

#### Статистика

- Используется **генеральное стандартное отклонение** ($\sqrt{\frac{1}{N} \sum (x - \mu)^2}$), так как замеры производятся над всей конечной совокупностью запланированных тестовых запросов, а не над случайной выборкой из непрерывного потока.
- Запросы, завершившиеся сетевой ошибкой или кодами 4xx/5xx, исключаются из расчёта средних скоростей, чтобы не искажать реальную пропускную способность, но при этом явно отражаются в общем счетчике сбоев.

### Запуск тестов

```bash
# Только быстрые офлайн юнит-тесты (без сетевых вызовов)
uv run pytest -m "not integration" -v

# Полный набор тестов (включая реальные интеграционные запросы в сеть)
uv run pytest -v

# Проверка строгой статической типизации
uv run mypy speedtest tests
```

### Планы по развитию

- Экспорт результатов в форматы JSON и CSV для интеграции в CI/CD и пайплайны мониторинга.
- Флаг `--compare`: сохранение результатов в файл и наглядный diff производительности "до и после подключения VPN".
- Сравнение протоколов HTTP/2, HTTP/1.1 и HTTP/3 (QUIC).
- Замер скорости отдачи (upload speed) через потоковые HTTP PUT/POST запросы.
- Расчёт перцентилей задержки ($p_{50}$, $p_{90}$, $p_{99}$).

## License

MIT
