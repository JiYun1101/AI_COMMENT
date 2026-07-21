from src.recommender.safety_filter import get_block_reason, is_safe_comment


def test_blocks_direct_profanity():
    assert get_block_reason("닥쳐!....이게 정답이네...") == "profanity"
    assert get_block_reason("멍청아 그것도 모르냐") == "profanity"
    assert get_block_reason("뭔 개소리여 이건") == "profanity"


def test_blocks_hate_speech():
    assert get_block_reason("전형적인 한남충 사고방식이네") == "hate_speech"
    assert get_block_reason("틀딱 소리 좀 그만해") == "hate_speech"


def test_blocks_spam():
    assert get_block_reason("구독 좀 눌러주세요 부탁드려요") == "spam"
    assert get_block_reason("자세한건 http://example.com 참고하세요") == "spam"


def test_blocks_threat():
    assert get_block_reason("죽여버릴거야 진짜") == "threat"


def test_length_bounds():
    assert get_block_reason("ㅋㅋ") == "too_short"
    assert get_block_reason("가" * 201) == "too_long"


def test_does_not_block_idiomatic_expressions():
    # "죽어라 노력해라" = 열심히 하라는 뜻의 흔한 관용구, 위협 아님
    assert is_safe_comment("죽어라 노력해서 성공해야 합니다")
    # "이 노래 죽인다" = 슬랭으로 최고라는 뜻, 위협 아님
    assert is_safe_comment("이 노래 진짜 죽인다")


def test_does_not_block_words_spanning_unrelated_terms():
    # "다시 발리에" -> 공백 제거 시 "시발" 포함되어 오탐났던 케이스
    assert is_safe_comment("슬기야, 만약 다시 발리에 간다면 꼭 가봐야 해")
    # "착한 남편" -> 공백 제거 시 "한남" 포함되어 오탐났던 케이스
    assert is_safe_comment("정말 착한 남편을 두셨네요")


def test_does_not_block_dakcyeo_ol_compound_verb():
    # "닥쳐오다/닥쳐올" = 다가오다, "닥쳐"(입 다물다)와 무관한 동사
    assert is_safe_comment("우리에게도 닥쳐올 수 있는 일입니다 조심하세요")


def test_does_not_block_topic_discussion_of_hate():
    # "혐오"라는 단어 자체를 다루는 정상적인 사회 논의는 차단하지 않는다
    assert is_safe_comment("혐오와 갈등은 어디서 만들어지는지 생각해볼 문제입니다")


def test_does_not_block_negative_opinion_without_abuse():
    assert is_safe_comment("이 음식점은 솔직히 최악이었어요 다시는 안 갈 것 같아요")


def test_does_not_block_normal_subscriber_comment():
    # 시청자가 스스로 구독했다고 밝히는 정상 댓글 (스팸 요청과 구분)
    assert is_safe_comment("영상 잘 보고 구독하고 갑니다 응원해요")
