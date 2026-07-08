def generate_candidates(post_text: str) -> list[dict]:
    return [
        {
            "type": "insight",
            "comment": "결국 핵심은 기술 자체보다 그 기술을 어떻게 활용하느냐인 것 같아요.",
        },
        {
            "type": "insight",
            "comment": "중요한 건 AI가 대체하느냐보다, 사람이 어떤 질문을 던지느냐인 듯합니다.",
        },
        {
            "type": "casual",
            "comment": "이건 생각보다 현실적인 문제라 더 와닿네요 ㅋㅋ",
        },
        {
            "type": "insight",
            "comment": "코드를 치는 능력보다 문제를 정의하고 설계하는 능력이 더 중요해질 것 같아요.",
        },
        {
            "type": "empathy",
            "comment": "이 부분은 진짜 많은 사람들이 공감할 만한 내용이네요.",
        },
        {
            "type": "question",
            "comment": "이 내용을 실제로 적용할 때 가장 어려운 점은 무엇일까요?",
        },
    ]