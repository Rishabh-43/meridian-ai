import re


class TextProcessor:

    @staticmethod
    def clean(text: str) -> str:
        """
        Normalize extracted document text.
        """

        if not text:
            return ""

        # Normalize line endings
        text = text.replace("\r\n", "\n")
        text = text.replace("\r", "\n")

        # Replace tabs with spaces
        text = text.replace("\t", " ")

        # Collapse multiple spaces
        text = re.sub(r"[ ]{2,}", " ", text)

        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()