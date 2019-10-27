import logging
import StringIO


def setup_logging(level=logging.WARN, keep_internal_copy=True):
    # global logging properties
    logger_global = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)s: %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger_global.addHandler(handler)
    logger = logging.getLogger(__name__)
    logger.setLevel(level)

    if keep_internal_copy:
        output_str = StringIO.StringIO()
        handler_internal = logging.StreamHandler(output_str)
        handler_internal.setFormatter(formatter)
        logger_global.addHandler(handler_internal)
        logger.output_str = output_str

    return logger