from joblib import load

#Load the saved model
text_clf_loaded = load('topic_model_ua.joblib')

#Test the model
test_text = ['Я дивлюся матч Манчестер Юнайтед', 'Україна підписала угоду з Євросоюзом', 'Акції Tesla зросли на 10%']
predicted = text_clf_loaded.predict(test_text)

# Print the predicted topic names
print(predicted)