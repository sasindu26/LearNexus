import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer
import string

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

class DescriptionPreprocessor:
    def __init__(self):
        self.stop_words = set(stopwords.words('english'))
        self.stemmer = PorterStemmer()
        
    def clean_text(self, text):
        """Remove HTML tags, special characters, and normalize text"""
        if not text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove special characters but keep alphanumeric and spaces
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
        
        # Remove extra whitespaces
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def tokenize_and_filter(self, text):
        """Tokenize text and filter stopwords and short words"""
        if not text:
            return []
        
        # Convert to lowercase and tokenize
        tokens = word_tokenize(text.lower())
        
        # Filter tokens: remove stopwords, punctuation, and short words
        filtered_tokens = [
            token for token in tokens 
            if token not in self.stop_words 
            and token not in string.punctuation 
            and len(token) > 2
            and token.isalpha()  # Only alphabetic tokens
        ]
        
        return filtered_tokens
    
    def stem_tokens(self, tokens):
        """Apply stemming to tokens"""
        return [self.stemmer.stem(token) for token in tokens]
    
    def preprocess_description(self, description):
        """Complete preprocessing pipeline"""
        # Step 1: Clean text
        cleaned_text = self.clean_text(description)
        
        # Step 2: Tokenize and filter
        tokens = self.tokenize_and_filter(cleaned_text)
        
        # Step 3: Apply stemming
        stemmed_tokens = self.stem_tokens(tokens)
        
        # Step 4: Join tokens back to text
        preprocessed_text = ' '.join(stemmed_tokens)
        
        return {
            'cleaned_text': cleaned_text,
            'tokens': tokens,
            'stemmed_tokens': stemmed_tokens,
            'preprocessed_text': preprocessed_text
        }

# Example usage
if __name__ == "__main__":
    preprocessor = DescriptionPreprocessor()
    
    sample_text = """
    <h1>Building Modern Web Applications</h1>
    <p>This article discusses how to build scalable web applications using React.js and Node.js.
    We'll cover best practices, performance optimization, and deployment strategies.
    Visit https://example.com for more information!</p>
    """
    
    result = preprocessor.preprocess_description(sample_text)
    print("Original:", sample_text)
    print("\nCleaned:", result['cleaned_text'])
    print("\nTokens:", result['tokens'])
    print("\nStemmed:", result['stemmed_tokens'])
    print("\nPreprocessed:", result['preprocessed_text'])