import logging
import json
import time
from google.cloud import logging as gcp_logging
from google.cloud.logging.handlers import CloudLoggingHandler

class JsonFormatter(logging.Formatter):
    """
    Custom logging formatter to output logs in a structured JSON format,
    compatible with Google Cloud Logging.
    """
    def format(self, record):
        log_entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": time.time(),
            "python_logger": record.name,
            "python_module": record.module,
            "python_function": record.funcName,
            "python_lineno": record.lineno,
            "trace_id": getattr(record, 'trace_id', None),
            "span_id": getattr(record, 'span_id', None),
        }
        # Add extra attributes (e.g., from `extra={"json_payload": ...}`)
        if hasattr(record, 'json_payload') and isinstance(record.json_payload, dict):
            log_entry.update(record.json_payload)
        return json.dumps(log_entry)

def setup_cloud_logging(gcp_project_id: str, inference_log_name: str, metrics_log_name: str):
    """
    Sets up Google Cloud Logging for the FastAPI application.

    Args:
        gcp_project_id (str): Your Google Cloud Project ID.
        inference_log_name (str): The name for inference-related logs.
        metrics_log_name (str): The name for vLLM metrics-related logs.

    Returns:
        tuple: A tuple containing (inference_logger, metrics_logger).
    """
    # Initialize GCP Logging client
    gcp_logging_client = gcp_logging.Client(project=gcp_project_id)

    # Set up the main logger for inference requests (model input/output)
    inference_logger = logging.getLogger(inference_log_name)
    inference_logger.setLevel(logging.INFO)
    inference_handler = CloudLoggingHandler(gcp_logging_client, name=inference_log_name)
    inference_handler.setFormatter(JsonFormatter())
    inference_logger.addHandler(inference_handler)
    inference_logger.propagate = False # Prevent logs from propagating to the root logger

    # Configure the root logger to output to console for local debugging.
    # This will only catch logs not handled by inference_logger or metrics_logger.
    root_logger = logging.getLogger()
    root_logger.handlers = [] # Clear existing handlers (like default basicConfig)
    root_logger.addHandler(logging.StreamHandler()) # Add console output
    root_logger.setLevel(logging.INFO) # Set a default level for console output

    return inference_logger

def flush_cloud_loggers(loggers: list[logging.Logger]):
    """
    Flushes all CloudLoggingHandler instances associated with the given loggers.
    """
    for logger in loggers:
        for handler in logger.handlers:
            if isinstance(handler, CloudLoggingHandler):
                handler.flush()
