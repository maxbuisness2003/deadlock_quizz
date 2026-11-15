name: Баг-репорт

description: Что-то на сайте работает не так
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        Спасибо за баг-репорт! Чем подробнее описание, тем быстрее починим.

  - type: textarea
    id: what
    attributes:
      label: Что произошло
      description: Опишите проблему своими словами
    validations:
      required: true

  - type: textarea
    id: expected
    attributes:
      label: Что ожидалось
    validations:
      required: true

  - type: textarea
    id: steps
    attributes:
      label: Как воспроизвести
      placeholder: |
        1. Открыть http://127.0.0.1:8001
        2. Нажать «Начать игру»
        3. ...
    validations:
      required: true

  - type: input
    id: version
    attributes:
      label: Версия / окружение
      placeholder: Windows 11, Python 3.12, Chrome 140
    validations:
      required: false

  - type: textarea
    id: logs
    attributes:
      label: Логи или скриншот
      description: Вывод консоли браузера или скриншот со страницы
    validations:
      required: false
