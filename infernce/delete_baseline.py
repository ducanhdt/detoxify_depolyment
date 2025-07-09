import json
import re
from typing import Optional, Set

import jieba
from datasets import load_dataset


class DetoxificationBaseline:
    """
    A class for implementing a baseline toxic text detoxification approach.
    The baseline removes toxic terms identified in a multilingual lexicon.

    Attributes:
        stopwords (Set[str]): A set of toxic terms to remove
        spaces_re (re.Pattern): Compiled regex for whitespace matching
    """

    def __init__(self, toxic_lexicon_path: Optional[str] = None):
        """
        Initialize the detoxification baseline.

        Args:
            toxic_lexicon_path: Optional path to load custom toxic lexicon.
                              If None, uses default multilingual lexicon.
        """
        self.spaces_re = re.compile(r"\s+")
        self.stopwords = self._load_toxic_lexicon(toxic_lexicon_path)

    def _load_toxic_lexicon(
        self,
        path: Optional[str] = None,
        hf_dataset_name: str = "textdetox/multilingual_toxic_lexicon",
    ) -> Set[str]:
        """
        Load toxic lexicon from HuggingFace datasets or local path.

        Args:
            path: Optional path to local lexicon file

        Returns:
            Set of toxic terms
        """
        if path:
            with open(path) as f:
                return set(json.load(f))

        stopwords_dataset = load_dataset(hf_dataset_name)
        words = []

        for language in stopwords_dataset.keys():
            words.extend(stopwords_dataset[language]["text"])

        return set(words)

    def detoxify(
        self,
        text: str,
        language: str = "en",
        remove_all_terms: bool = False,
        remove_no_terms: bool = False,
    ) -> str:
        """
        Remove toxic terms from input text based on language.

        Args:
            text: Input text to detoxify
            language: Language code ('zh' for Chinese, others for space-separated)
            remove_all_terms: If True, returns empty string (for testing)
            remove_no_terms: If True, returns original text (for testing)

        Returns:
            Detoxified text
        """
        if remove_no_terms:
            return text
        if remove_all_terms:
            return ""

        if language != "zh":
            tokens = [
                token
                for token in self.spaces_re.split(text)
                if token.lower().strip() not in self.stopwords
            ]
            return " ".join(tokens)
        else:
            return "".join([x for x in jieba.cut(text) if x not in self.stopwords])

    def find_toxic_terms(
        self,
        text: str,
        language: str = "en") -> Set[str]:
        """
        Find toxic terms in the input text based on language.
        Args:
            text: Input text to check for toxic terms
            language: Language code ('zh' for Chinese, others for space-separated)
        Returns:
            Set of toxic terms found in the text
        """
        if language != "zh":
            tokens = self.spaces_re.split(text)
            toxic_terms = set(token for token in tokens if token.lower().strip() in self.stopwords)
        else:
            toxic_terms = set(x for x in jieba.cut(text) if x in self.stopwords)
        return toxic_terms
    