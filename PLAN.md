# ai-sre-agent — план (pet project)

Read-only агент: примерно через 5 минут после алерта присылает в Slack или Telegram гипотезу причины с доказательствами и предлагаемый фикс. Бэктест на chaos-сценариях доказывает, что это работает.

## Зачем

AI ускорил разработку: PR и деплоев стало в разы больше, а с ними растёт и число инцидентов. Инциденты = изменения × вероятность сбоя; по данным Rootly, страниц вне рабочего времени почти вдвое больше.

Получается круг: AI вносит изменения быстрее, чем команда успевает разбирать их последствия. Команда эксплуатации не растёт вместе с числом деплоев, и узким местом становится расследование — найти причину и понять, что откатить.

Агент закрывает круг с другой стороны: раз AI ускоряет поставку, он же должен ускорять разбор инцидентов. Он сразу собирает метрики, логи и последние изменения, проверяет гипотезы и приносит причину с доказательствами и проверенным фиксом. Время до восстановления сокращается.

Источник: https://newsletter.pragmaticengineer.com/p/ai-sre

## Метрики

| Метрика | Как меряем | Цель |
|---|---|---|
| Точность root cause (top-1 / top-3) | Бэктест, причина известна заранее | ≥ 70% / ≥ 85% |
| Время до первой гипотезы | Firing алерта → сообщение в Slack | медиана < 5 мин |
| Фикс агента чинит | Скрипт применяет mitigation, сервис восстановился? | ≥ 6 из 8 |
| Время до восстановления | Алерт → зелёный SLO по совету агента | медиана < 10 мин |
| Срезанные страницы (потом) | Triage в shadow mode против ручной разметки | −30…50% «будить» |
| Стоимость расследования | Токены × цена или GPU-минуты | < $0.05 |
| Ложные «уверенные» ответы | Verifier пропустил неверное | ≤ 1 на 8 сценариев |

Цели — ориентиры. В CV идут только измеренные цифры.

## Архитектура

```
Alertmanager ──webhook──> Orchestrator (Python asyncio)
                               │
                               v
   Read-only MCP tools <──> Investigators (параллельно) <──> LLM (vLLM, Qwen 7–14B)
   - Prometheus (PromQL)      - деплои и конфиг              ^
   - логи (Loki)              - ресурсы и лимиты             │
   - K8s get/list/watch       - Kafka, Postgres, сеть    RAG: runbook'и в pgvector
   - Argo CD + git history         │                     (отдельный Postgres агента)
                                   v
                              Verifier (без доказательств — отказ)
                                   │
                                   v
   Аудит-лог <──────────── Slack/Telegram: причина + доказательства + фикс
   (= датасет бэктеста)            │
                                   v
                              Инженер решает и действует
```

Стенд: voting-app (Kafka/Strimzi, PostgreSQL на CloudNativePG, Redis, KEDA; MongoDB убираем) — это «прод», который ломаем. gpu-inference-platform даёт LLM для агента. Связь между ними только через `LLM_BASE_URL`.

## Guardrails

- [x] RBAC: ServiceAccount и ClusterRole только get/list/watch, без secrets и pods/exec. CI-тест: `kubectl auth can-i` возвращает no на delete/exec/patch.
- [x] Allowlist: только свои MCP-инструменты с фиксированными параметрами, без свободного shell.
- [x] Лимиты: таймаут на вызов, максимум шагов и токенов, лимит параллельных субагентов.
- [x] Доказательства: каждая гипотеза несёт запрос и результат; verifier отклоняет гипотезы без доказательств.
- [x] Редакция: токены, пароли, IP и e-mail маскируются до отправки в LLM; внешний API — только после редакции, флагом.
- [x] Аудит-лог каждого расследования: вход, вызовы, ответы, итог.
- [ ] Mitigation — это текст («rollback app X на ревизию N»). Исполняет человек или скрипт бэктеста. У скрипта свой ServiceAccount с правами на запись, у агента их нет.

## Сценарии бэктеста

Скрипт на каждый сценарий: сломать → дождаться алерта → прогнать агента → сравнить с правильной причиной → применить фикс → замерить восстановление → откатить. Правильный ответ записывается в файл до запуска агента.

| # | Сценарий | Как сломать | Правильная причина | Этап |
|---|---|---|---|---|
| 1 | Плохой деплой | Argo CD sync на несуществующий тег образа | ImagePullBackOff, ревизия N | ядро |
| 2 | Регрессия после деплоя | Неверная env-переменная в новой версии | 5xx после sync, конфиг | ядро |
| 3 | Падение Kafka-брокера | Удалить под брокера Strimzi | Under-replicated partitions, lag | ядро |
| 4 | Postgres failover | Удалить primary в CNPG под нагрузкой k6 | Switchover, ошибки записи | ядро |
| 5 | Пул соединений Postgres | Занизить max_connections / утечка под k6 | too many connections, 5xx | ядро |
| 6 | Лаг реплики Postgres | Чтения через ro-сервис CNPG + тяжёлая запись, ограничить I/O реплики | Replication lag, устаревшие чтения | ядро |
| 7 | Redis OOM | Урезать memory limit | OOMKilled | ядро |
| 8 | Шум (triage) | Флапающий алерт после деплоя | Не будить — шум | ядро |
| 9 | Consumer lag | KEDA maxReplicas = 1 под k6 | Потолок автоскейла | потом |
| 10 | CPU throttling | Урезать CPU limit | Рост latency, throttling | потом |
| 11 | Disk pressure | Заполнить PVC Postgres | PVC full, WAL не пишется | потом |
| 12 | NetworkPolicy | Запретить app → Postgres | Таймауты соединения | потом |
| 13 | Сертификат | Просроченный TLS-секрет на ingress | TLS handshake errors | потом |
| 14 | Секрет | Неверный пароль Postgres в Secret | Auth failed, CrashLoop | потом |
| 15 | Два сбоя сразу | #3 + #10 | Обе причины, top-3 | потом |

## План — 2 недели

Неделя 1 сделана быстрее плана, поэтому неделя 2 начинается сразу. После неё будет рабочий агент с измеренными цифрами и строка для CV. Всё остальное — в «Потом».

### Неделя 1 — стенд и первый агент (готово)

- [x] k3s/kind + Prometheus, Alertmanager, Grafana, Loki (легче, чем ELK)
- [x] Переписать слой данных voting-app под Postgres (vote_id UNIQUE + `INSERT ... ON CONFLICT DO NOTHING`) и заново проверить exactly-once через k6 с убийством consumer — главная задача недели
- [x] 8 алертов и короткий runbook на каждый (markdown в репо), ссылка в аннотации. Это же корпус для RAG
- [x] Chaos-сценарии 1, 3, 4, 5, 7 скриптами
- [x] Read-only MCP-сервер: PromQL, логи, K8s events/describe, Argo CD history, git log gitops-репо
- [x] Один агент: webhook Alertmanager → сообщение в Slack/Telegram

### Неделя 2 — точность, бэктест, упаковка

- [x] Investigators по классам гипотез параллельно в asyncio + verifier, который отклоняет гипотезы без доказательств (точнее одного агента не стал, см. README)
- [x] RAG по runbook'ам: эмбеддинги в pgvector в отдельном Postgres агента (не в БД voting-app — её ломают сценарии 4–6). Агент подтягивает top-3 runbook'а в контекст. Прошлые расследования в корпус бэктеста не кладём, иначе агент «подсмотрит» ответ
- [x] Сценарии 2, 6, 8 + раннер бэктеста → таблица результатов по 8 сценариям
- [ ] MLflow (сервер в кластере, backend — тот же Postgres агента): каждый прогон бэктеста — это run с моделью, версией промпта, точностью, временем и стоимостью. Трейсы LLM-вызовов через MLflow Tracing; лучшая связка промпта и модели — в registry (tracking и tracing готовы; registry — вместе с абляцией)
- [x] Метка в отчёте «будить / до утра / шум», проверка на сценарии 8
- [ ] Применять предложенные фиксы скриптом и засекать время до восстановления SLO
- [ ] Один прогон на vLLM (Spot GPU) → стоимость расследования
- [x] Baseline на правилах (без LLM) на тех же 8 сценариях — показывает, где LLM действительно нужен
- [ ] Абляция через тот же раннер, флагами в конфиге, всё в MLflow:
  - один агент против investigators + verifier (главное — ложные «уверенные» ответы)
  - с RAG и без RAG
  - Qwen 7B против 14B AWQ на vLLM, в тот же заход на GPU
  - стабильность: каждый сценарий 3 прогона, совпадает ли причина
- [ ] README с цифрами и GIF; пост в LinkedIn

### Потом, если зайдёт

- Карта зависимостей сервисов (лейблы K8s + YAML) как контекст
- Triage в shadow mode на реальном потоке алертов
- Память: заметки по прошлым инцидентам, противоречащие — в карантин
- Метрики агента в Prometheus (длительность, токены, стоимость) + дашборд Grafana
- Сравнение других семейств моделей по цене и точности
- Argo Rollouts canary + автооткат по burn-rate SLO; агент ссылается на откат как на mitigation
- Сценарии 9–15
- Сравнение с HolmesGPT на тех же сценариях
- Бэктест в CI: точность упала — сборка красная
- Черновик постмортема из аудит-лога
- Helm-чарт агента + деплой через Argo CD

## Что закрывает по MLOps / AI

**Закрывает:** production Python, MLflow (tracking, tracing, registry), RAG + vector DB (pgvector), агенты и tool calling, LLM eval, vLLM в реальной задаче.

**Не закрывает:** Kubeflow, Airflow, Ray, Run:ai/Kueue, Triton, SageMaker/Bedrock, обучение моделей.

## LLM и стоимость

- Разработка: k3s/kind локально, внешний API за флагом редакции или маленькая локальная модель.
- Бэктест и демо: EKS + Spot A10G из gpu-inference-platform, vLLM, модель класса Qwen 7–14B Instruct с tool calling. Замер ~$0.09 за 1M токенов.
- Микс моделей (потом, после 7B против 14B): investigator — быстрая и меньшая модель, verifier — сильнее. Сравнить в бэктесте.
- Один OpenAI-совместимый клиент: vLLM и внешний API переключаются конфигом.

Открытый вопрос: тянет ли выбранная модель многошаговый tool calling. Проверить в начале недели 2 на одном сценарии, до полного бэктеста.

## Строка для CV (заполнить после недели 2: N, X, M, R, Y, Z)

AI SRE incident-investigation agent (pet project) — read-only agent on Kubernetes that turns an Alertmanager alert into a root-cause hypothesis with evidence (Prometheus, logs, K8s events, Argo CD history) in Slack. Investigator + verifier agents, self-hosted LLM on vLLM. Backtested on N chaos scenarios: X/N correct root cause, suggested fix restored service in M/N with median R min to recovery, median Y min to first hypothesis, ~$Z per investigation. Tech: Python asyncio, MCP, MLflow (tracking, tracing), RAG on pgvector, Kubernetes RBAC, Prometheus, Argo CD, Strimzi Kafka, PostgreSQL (CloudNativePG), vLLM.
