class PersianNumbers:
    @staticmethod
    def to_persian(text: str) -> str:
        persian_digits = {
            '0': '۰',
            '1': '۱', 
            '2': '۲',
            '3': '۳',
            '4': '۴',
            '5': '۵',
            '6': '۶',
            '7': '۷',
            '8': '۸',
            '9': '۹'
        }
        
        for english, persian in persian_digits.items():
            text = text.replace(english, persian)
        return text
    
    @staticmethod
    def to_english(text: str) -> str:
        english_digits = {
            '۰': '0',
            '۱': '1',
            '۲': '2', 
            '۳': '3',
            '۴': '4',
            '۵': '5',
            '۶': '6',
            '۷': '7',
            '۸': '8',
            '۹': '9'
        }
        
        for persian, english in english_digits.items():
            text = text.replace(persian, english)
        return text
