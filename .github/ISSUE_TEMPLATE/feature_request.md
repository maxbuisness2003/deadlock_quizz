name: Идея или предложение

description: Новая фича или улучшение
labels: ["enhancement"]
body:
  - type: textarea
    id: idea
    attributes:
      label: Что хочется добавить
    validations:
      required: true

  - type: textarea
    id: why
    attributes:
      label: Зачем это нужно
    validations:
      required: true

  - type: textarea
    id: alternatives
    attributes:
      label: Рассматриваемые варианты
    validations:
      required: false
