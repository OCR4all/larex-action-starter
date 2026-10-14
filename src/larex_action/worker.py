# SPDX-License-Identifier: MIT
from __future__ import annotations

import logging
from dataclasses import dataclass
from multiprocessing.connection import Connection

from .config import env

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if env.ACTION_DEBUG else logging.INFO)


@dataclass
class WorkerRequest:
    """ Worker inputs """
    # TEMPLATE: Add or change fields for action inputs. Example:
    # image: bytes
    # xml: bytes
    

@dataclass
class WorkerSuccess:
    """ Worker outputs on success """
    # TEMPLATE: Add or change fields for action outputs. Example:
    # xml: bytes
    

@dataclass
class WorkerFailure:
    """ Worker output on failure """
    error: str


# TEMPLATE: accept passes parameters. Example:
# def worker(connection: Connection, model: Path) -> None:
def worker(connection: Connection) -> None:
    """
    Process-isolated action worker.
    
    Request input with `request = connection.recv()`.
    Send output with `connection.send(obj)`.
    """
    logger.debug('Initialize worker')
    
    # TEMPLATE: import and initialize models here. Example:
    # import cv2
    # from my_model import Model
    # m = Model(model)
    
    while True:
        try:
            request = connection.recv()
        except EOFError:
            logger.debug('Parent closed pipe; shutting down worker')
            break
        if request is None:
            logger.debug('Parent sent shutdown signal; shutting down worker')
            break   
        if not isinstance(request, WorkerRequest):
            logger.error(f'Received unexpected request: {type(request).__name__}')
            continue
        
        try:
            # TEMPLATE: process pages here. Example:
            # image = cv2.imdecode(np.frombuffer(request.image, np.uint8), cv2.IMREAD_GRAYSCALE)
            # ...
            
            # TEMPLATE: send results with the WorkerSuccess dataclass. Example:
            # connection.send(WorkerSuccess(image))
            connection.send(WorkerSuccess())
            
        except Exception as exc:
            logger.exception('Failed to process element')
            try:
                connection.send(WorkerFailure(f'{type(exc).__name__} {exc}'))
            except (BrokenPipeError, EOFError, OSError):
                logger.warning('Could not send worker failure to parent')
                break
    
    connection.close()
    logger.info('Worker stopped successfully')
