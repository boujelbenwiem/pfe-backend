import os
import time
import opik
from opik.evaluation import evaluate
from opik.evaluation.metrics import Hallucination
from app.core.config import settings

# LiteLLM (used by Opik metrics) requires GROQ_API_KEY as an env var
os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY


client = opik.Opik(
    api_key=settings.OPIK_API_KEY,
    workspace=settings.OPIK_WORKSPACE,
)

dataset = client.get_dataset(name="hallucination-eval", project_name="bv-multi-agent")

def evaluation_task(item):
    time.sleep(2)
    return {"output": item["output"]}

hallucination_metric = Hallucination(model="groq/ss-120bgpt-o")

result = evaluate(
    dataset=dataset,
    task=evaluation_task,
    scoring_metrics=[hallucination_metric],
    experiment_name="hallucination-baseline",
    project_name="bv-multi-agent",
    
)

print(f"Experiment: {result.experiment_name}")
print(f"URL: {result.experiment_url}")