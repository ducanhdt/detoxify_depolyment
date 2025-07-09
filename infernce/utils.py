from prompts import ru, uk, hi, en, es, fr, de, it, tt, zh, ja, am, he, hin, ar

langs = ['en', 'es', 'fr', 'de', 'it', 'tt', 'zh', 'ja', 'ru', 'uk', 'hi', 'am', 'he', 'hin', 'ar']
system_prompt= { lang: eval(lang).system_prompt for lang in langs }
input_format = { lang: eval(lang).input_format for lang in langs }
output_format = { lang: eval(lang).output_format for lang in langs }
example = { lang: eval(lang).example for lang in langs }
toxic_words_key = {
    'en': 'toxic_words',
'es': 'palabras_toxicas',
'fr': 'mots_toxiques',
'de': 'toxische_Wörter',
'it': 'parole_tossiche',
'tt': 'токсик_сүзләр',
'zh': '有毒词语',
'ja': '有害な単語',
'ru': 'токсичные_слова',
'uk': 'токсичні_слова',
'hi': 'विषाक्त शब्द',
'am': 'ጎጂ_ቃላት',
'he': 'מילים_רעילות',
'hin': 'Toxic shabd',
'ar': 'الكلمات_السامة',
}
neutral_text_key = {
'en': 'neutral_text',
'es': 'texto_neutral',
'fr': 'texte_neutre',
'de': 'neutraler_Text',
'it': 'testo_neutro',
'tt': 'нейтраль_текст',
'zh': '中性文本',
'ja': '中立的なテキスト',
'ru': 'нейтральный_текст',
'uk': 'нейтральний_текст',
'hi': 'तटस्थ पाठ',
'am': 'ጉዳት_የሌለው_ጽሑፍ',
'he': 'טקסט_ניטרלי',
'hin': 'Neutral text',
'ar': 'النص_المحايد'
}
toxic_words_key_dict = {
'en': 'toxic_words',
'es': 'palabras_toxicas',
'fr': 'mots_toxiques',
'de': 'toxische_Wörter',
'it': 'parole_tossiche',
'tt': 'токсик_сүзләр',
'zh': '有毒词语',
'ja': '有害な単語',
'ru': 'токсичные_слова',
'uk': 'токсичні_слова',
'hi': 'विषाक्त शब्द',
'am': 'ጎጂ_ቃላት',
'he': 'מילים_רעילות',
'hin': 'toxic_words',
'ar': 'الكلمات_السامة',
}
neutral_text_key_dict = {
'en': 'neutral_text',
'es': 'texto_neutral',
'fr': 'texte_neutre',
'de': 'neutraler_Text',
'it': 'testo_neutro',
'tt': 'нейтраль_текст',
'zh': '中性文本',
'ja': '中立的なテキスト',
'ru': 'нейтральный_текст',
'uk': 'нейтральний_текст',
'hi': 'तटस्थ पाठ',
'am': 'ጉዳት_የሌለው_ጽሑፍ',
'he': 'טקסט_ניטרלי',
'hin': 'neutral_text',
'ar': 'النص_المحايد'
}

def get_messages(text:str , lang:str):
    input_message = input_format[lang].format(lang=lang, toxic_sentence=text)

    messages = [
        {"role": "system", "content": system_prompt[lang]},
        {"role": "user", "content": input_message},
    ]
    return messages

toxic_words_key_dict = {
    'en': 'toxic_words',
'es': 'palabras_toxicas',
'fr': 'mots_toxiques',
'de': 'toxische_Wörter',
'it': 'parole_tossiche',
'tt': 'токсик_сүзләр',
'zh': '有毒词语',
'ja': '有害な単語',
'ru': 'токсичные_слова',
'uk': 'токсичні_слова',
'hi': 'विषाक्त शब्द',
'am': 'ጎጂ_ቃላት',
'he': 'מילים_רעילות',
'hin': 'toxic_words',
'ar': 'الكلمات_السامة',
}
neutral_text_key_dict = {
    'en': 'neutral_text',
'es': 'texto_neutral',
'fr': 'texte_neutre',
'de': 'neutraler_Text',
'it': 'testo_neutro',
'tt': 'нейтраль_текст',
'zh': '中性文本',
'ja': '中立的なテキスト',
'ru': 'нейтральный_текст',
'uk': 'нейтральний_текст',
'hi': 'तटस्थ पाठ',
'am': 'ጉዳት_የሌለው_ጽሑፍ',
'he': 'טקסט_ניטרלי',
'hin': 'neutral_text',
'ar': 'النص_المحايد'
}
def parse_detoxified_output(output_text, lang):
    """
    Parse the detoxification output in YAML format.
    
    Args:
        output_text (str): The YAML-formatted output from the detoxification model
        
    Returns:
        dict: A dictionary containing the toxic words and neutral text
    
    Example:
        >>> output = '''toxic_words: ["idiot", "stupid"]
        neutral_text: You are not very smart.'''
        >>> parse_detoxified_output(output)
        {'toxic_words': ['idiot', 'stupid'], 'neutral_text': 'You are not very smart.'}
    """
    result = {}
    try:
        toxic_words_key = toxic_words_key_dict[lang]
        neutral_text_key = neutral_text_key_dict[lang]
        
        toxic_words_match = output_text.find(toxic_words_key)
        neutral_text_match = output_text.find(neutral_text_key)
        
        if toxic_words_match == -1 or neutral_text_match == -1:
            raise ValueError("Output format is incorrect. Expected 'toxic_words:' and 'neutral_text:' fields.")
        
        # Extract toxic words
        toxic_words_text = output_text[toxic_words_match + len(toxic_words_key)+1:neutral_text_match].strip()
        
        # Parse toxic words as a list
        if toxic_words_text.startswith("[") and toxic_words_text.endswith("]"):
            # Handle list format
            toxic_words_text = toxic_words_text[1:-1]  # Remove brackets
            if toxic_words_text:
                # Split by comma, remove quotes, and strip whitespace
                result["toxic_words"] = [word.strip().strip('"\'') for word in toxic_words_text.split(",")]
            else:
                result["toxic_words"] = []
        else:
            # Handle single item or empty
            if toxic_words_text:
                result["toxic_words"] = [toxic_words_text.strip().strip('"\'')]
            else:
                result["toxic_words"] = []
        
        # Extract neutral text
        neutral_text = output_text[neutral_text_match + len(neutral_text_key)+1:].strip()
        result["neutral_text"] = neutral_text if '\n' not in neutral_text else neutral_text.split('\n')[0]
        
        return result
    except:
        print("Prase error with ", output_text)
        return {"toxic_words":[], "neutral_text":"error"}
    