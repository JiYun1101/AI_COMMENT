# Comment Writer LangGraph

This graph is runnable from LangGraph or Python. It performs deterministic video context collection, then calls the **same** LLM generation, candidate validation, safety filtering and reaction ranker used by the production FastAPI route.

Flow: `START → ContextNode → RecommendNode → END`.

```python
from casts.comment_writer.graph import comment_writer_graph
result = comment_writer_graph.invoke({"video_url": "https://www.youtube.com/watch?v=VIDEO_ID", "top_k": 5})
print(result["recommendations"])
```

Environment requirements: YouTube Data API key, an available LLM provider, trained ranker model. The graph itself **does not post comments**. A future iteration can split generation/safety/ranking into separate nodes and add approval + retry state; posting remains behind the existing explicit-click flow.
