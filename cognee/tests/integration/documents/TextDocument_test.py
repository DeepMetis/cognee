import os
import uuid

import pytest
from cognee.modules.chunking.TextChunker import TextChunker
from cognee.modules.data.processing.document_types.TextDocument import TextDocument

GROUND_TRUTH = {
    "code.txt": [
        {"word_count": 252, "len_text": 1376, "cut_type": "paragraph_end"},
        {"word_count": 56, "len_text": 481, "cut_type": "paragraph_end"},
    ],
    "Natural_language_processing.txt": [
        {"word_count": 128, "len_text": 984, "cut_type": "paragraph_end"},
        {"word_count": 1, "len_text": 1, "cut_type": "paragraph_end"},
    ],
}


@pytest.mark.parametrize(
    "input_file,chunk_size",
    [("code.txt", 256), ("Natural_language_processing.txt", 128)],
)
def test_TextDocument(input_file, chunk_size):
    test_file_path = os.path.join(
        os.sep,
        *(os.path.dirname(__file__).split(os.sep)[:-2]),
        "test_data",
        input_file,
    )
    document = TextDocument(
        id=uuid.uuid4(),
        name=input_file,
        raw_data_location=test_file_path,
        external_metadata="",
        mime_type="",
    )

    for ground_truth, paragraph_data in zip(
        GROUND_TRUTH[input_file],
        document.read(chunk_size=chunk_size, chunker_cls=TextChunker, max_chunk_tokens=1024),
    ):
        assert ground_truth["word_count"] == paragraph_data.word_count, (
            f'{ground_truth["word_count"] = } != {paragraph_data.word_count = }'
        )
        assert ground_truth["len_text"] == len(paragraph_data.text), (
            f'{ground_truth["len_text"] = } != {len(paragraph_data.text) = }'
        )
        assert ground_truth["cut_type"] == paragraph_data.cut_type, (
            f'{ground_truth["cut_type"] = } != {paragraph_data.cut_type = }'
        )
