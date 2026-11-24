# SPDX-License-Identifier: MIT
import logging
from dataclasses import dataclass
from multiprocessing.connection import Connection
from typing import Literal

from .config import env

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if env.ACTION_DEBUG else logging.INFO)


@dataclass
class WorkerRequest:
    """ Inputs for the worker process """
    # TEMPLATE: Add or change fields for action inputs. Example:
    # image: bytes
    # xml: bytes


@dataclass
class WorkerResponse:
    """ Worker outputs on success """
    # TEMPLATE: Add or change fields for action outputs. Example:
    # xml: bytes


@dataclass
class WorkerStatus:
    """ Status message from the worker """
    type: Literal['loaded', 'error']
    message: str | None = None


def _send(connection: Connection, message: object) -> bool:
    """ Send a message to the parent. Returns False if the parent is gone. """
    try:
        connection.send(message)
    except OSError:
        logger.warning(f'Could not send {type(message).__name__} to parent')
        return False
    return True


# TEMPLATE: accept passes parameters. Example:
# def worker(connection: Connection, model: Path) -> None:
def worker(connection: Connection, ) -> None:
    """
    Process-isolated action worker.

    Protocol:
    1. Send exactly one `WorkerStatus` after startup: 'loaded', or 'error' followed by exit if loading failed.
    2. For every request (`request = connection.recv()`), send exactly one `WorkerResponse`
       or `WorkerStatus('error', ...)` (`connection.send(obj)`).
    3. Exit when `None` is received or the parent closes the pipe.
    """
    logger.debug('Initialize worker')

    with connection:
        try:
            # TEMPLATE: import and initialize models here. Example:
            # import cv2
            # from my_model import Model
            # m = Model(model)
            pass
        except Exception as exc:
            logger.exception('Failed to load worker')
            _send(connection, WorkerStatus('error', f'{type(exc).__name__} {exc}'))
            return

        if not _send(connection, WorkerStatus('loaded')):
            return

        while True:
            try:
                request = connection.recv()
            except (EOFError, OSError):
                logger.debug('Parent closed pipe; shutting down worker')
                break
            if request is None:
                logger.debug('Parent sent shutdown signal; shutting down worker')
                break

            try:
                if not isinstance(request, WorkerRequest):
                    raise TypeError(f'Unexpected request: {type(request).__name__}')

                # TEMPLATE: process pages here. Example:
                # image = cv2.imdecode(np.frombuffer(request.image, np.uint8), cv2.IMREAD_GRAYSCALE)
                # ...

                # TEMPLATE: send results with the WorkerResponse dataclass. Example:
                # connection.send(WorkerResponse(image))
                connection.send(WorkerResponse())

            except Exception as exc:
                logger.exception('Failed to process element')
                if not _send(connection, WorkerStatus('error', f'{type(exc).__name__} {exc}')):
                    break

    logger.info('Worker stopped successfully')
