"""Export functions for samenwijzer."""

from pathlib import Path


def export_results(analysis_results, output_path: Path) -> None:
    """Export analysis results to the output directory.

    Args:
        analysis_results: Output from analyze_learning_progress
        output_path: Target path for the exported file
    """
    raise NotImplementedError
