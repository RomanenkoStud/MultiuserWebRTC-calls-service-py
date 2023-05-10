from transformers import pipeline

# Load the fine-tuned BERT model
model = pipeline('text-classification', model='./fine-tuned-bert', tokenizer='bert-base-multilingual-uncased')

# Example usage
examples = [
"Apple запускає нові гаджети.",
"Україна отримала перемогу від Росії в суді про перехід Кримської протоки.",
"Вчені з університету MIT розробили нейронну мережу, яка може передбачити, які слова будуть вживані у реченні, заданому користувачем.",
"Компанія Tesla презентувала нову версію свого електромобіля.",
"Український банк оголосив про запуск нової програми кредитування.",
"У Києві відбулася велика концертна програма до Дня Незалежності України."
]

for text in examples:
    print(text)
    print(model(text)[0])