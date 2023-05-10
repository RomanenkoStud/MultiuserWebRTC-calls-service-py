#Import necessary libraries
from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from joblib import dump

#Load the Ukrainian News dataset
dataset = load_dataset('FIdo-AI/ua-news', split='train[:80%]')

#Extract the text and targets from the dataset
text = [item['text'] for item in dataset]
target = [item['target'] for item in dataset]

#Define the classification pipeline
text_clf = Pipeline([
('tfidf', TfidfVectorizer()),
('clf', MultinomialNB()),
])

#Train the model
text_clf.fit(text, target)

#Save the trained model to disk
dump(text_clf, 'topic_model_ua.joblib')