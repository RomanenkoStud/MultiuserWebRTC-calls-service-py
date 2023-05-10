from datasets import load_dataset
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from transformers.integrations import TensorBoardCallback

import multiprocessing

import torch

def main():
    # Load the pre-trained BERT tokenizer
    tokenizer = BertTokenizer.from_pretrained('bert-base-multilingual-uncased')

    # Tokenize the text data and add special tokens
    def tokenize_data(data):
        return tokenizer(data['text'], padding='max_length', truncation=True)

    label_map = {
        'політика': 0,
        'спорт': 1,
        'новини': 2,
        'бізнес': 3,
        'технології': 4
    }

    def map_labels(data):
        data['label'] = label_map[data['label']]
        return data

    # Load the dataset
    dataset = load_dataset('FIdo-AI/ua-news', split='train[:80%]')
    # Rename the target column to 'label'
    dataset = dataset.rename_column('target', 'label')
    dataset = dataset.map(map_labels)
    tokenized_dataset = dataset.map(tokenize_data, batched=True)

    # Load the pre-trained BERT model for sequence classification
    model = BertForSequenceClassification.from_pretrained('bert-base-multilingual-uncased', num_labels=5)
    
    # Move the model to the GPU device
    device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
    torch.cuda.empty_cache()
    model.to(device)

    # Define the training arguments
    training_args = TrainingArguments(
        output_dir='./results',          # Output directory
        evaluation_strategy='epoch',     # Run evaluation every epoch
        learning_rate=5e-5,              # Learning rate
        per_device_train_batch_size=4,  # Batch size for training
        per_device_eval_batch_size=4,   # Batch size for evaluation
        num_train_epochs=2,              # Number of training epochs
        weight_decay=0.01,               # Weight decay
        save_strategy='no',               # Disable saving checkpoints
        push_to_hub=False,               # Whether to push the model checkpoint to the hub
        logging_dir='./logs',            # Directory to write TensorBoard logs to
        logging_steps=100,               # Log every 100 training steps
        report_to='tensorboard',         # Enable TensorBoard reporting
        run_name='my_run_name',          # Name for the run in TensorBoard
        fp16=True,                       # Use mixed precision training
        gradient_accumulation_steps=4,   # Accumulate gradients over 4 small batches
    )

    # Load the evaluation dataset
    eval_dataset = load_dataset('FIdo-AI/ua-news', split='train[80%:]')
    eval_dataset = eval_dataset.rename_column('target', 'label')
    eval_dataset = eval_dataset.map(map_labels)
    eval_dataset = eval_dataset.map(tokenize_data, batched=True)

    # Define the Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        callbacks=[TensorBoardCallback],
        eval_dataset=eval_dataset,
    )

    # Train the model
    trainer.train()

    # Save the fine-tuned model
    model.save_pretrained('./fine-tuned-bert')

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()