"""모델 피처 스키마 단일 소스.

``train.py`` 와 ``predict.py`` 가 모두 import 하는 ``FEATURE_COLUMNS`` 를
여기서 단일 정의한다. 텍스트 피처는 ``text_features`` 의 추출기가,
임베딩 유사도 피처는 ``embedding_features`` 가 정의하므로, 컬럼 목록이
한 곳에서 파생되어 학습-추론 드리프트가 구조적으로 방지된다.
"""

from src.features.embedding_features import SIMILARITY_COLUMN
from src.features.text_features import TEXT_FEATURE_COLUMNS


FEATURE_COLUMNS = TEXT_FEATURE_COLUMNS + [SIMILARITY_COLUMN]
