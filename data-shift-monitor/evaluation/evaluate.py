import argparse
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent))

from metrics.fluency.xcomet import CometFluency
from metrics.similarity import SimilarityConfig, SimilarityMeasurement
from metrics.toxicity import ToxicityConfig, ToxicityMeasurement
import numpy as np

def eval(original_texts, rewritten_texts, reference_texts = None):
    if not reference_texts:
        reference_texts = rewritten_texts.copy()
    batch_size = 2
    efficient = False
    fluency_batch_size = 4
    device = "cpu"
    
    # Configure and run similarity measurement
    sim_config = SimilarityConfig(
        batch_size=batch_size,
        efficient_version=efficient,
        device=device,
    )
    similarity_measurer = SimilarityMeasurement(sim_config)
    sim_scores = similarity_measurer.evaluate_similarity(
        original_texts=original_texts,
        rewritten_texts=rewritten_texts,
        reference_texts=reference_texts,
    )

    # Configure and run toxicity measurement
    tox_config = ToxicityConfig(
        batch_size=batch_size,
        device=device,
    )
    toxicity_measurer = ToxicityMeasurement(tox_config)
    tox_scores = toxicity_measurer.compare_toxicity(
        original_texts=original_texts,
        rewritten_texts=rewritten_texts,
        reference_texts=reference_texts,
    )

    # Configure and run fluency measurement
    # fluency_measurer = CometFluency()

    # comet_input: list[dict[str, str]] = []
    # for original_sent, rewritten_sent, reference_sent in zip(
    #     original_texts, rewritten_texts, reference_texts
    # ):
    #     comet_input.append(
    #         {"src": original_sent, "mt": rewritten_sent, "ref": reference_sent}
    #     )

    # fluency_scores = fluency_measurer.get_scores(
    #     input_data=comet_input, batch_size=fluency_batch_size
    # )
    results = {}
    # Get Final Metric
    # J = np.array(sim_scores) * np.array(tox_scores) * np.array(fluency_scores)
    # results["J"] = J
    results["STA"] = tox_scores
    results["SIM"] = sim_scores
    # results["XCOMET"] = fluency_scores
    return results

if __name__ == "__main__":
    original_texts = ["What the hell is this?", "This is a test sentence."]
    rewritten_texts = ["What is this?", "This is a test."]
    reference_texts = None
    
    results = eval(original_texts, rewritten_texts, reference_texts)
    print(results)