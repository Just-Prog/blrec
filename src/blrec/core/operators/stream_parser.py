from __future__ import annotations

import io
import logging

from reactivex import Observable
from reactivex import operators as ops

from ...flv import operators as flv_ops
from ...flv.exceptions import FlvDataError
from ...flv.operators.typing import FLVStream
from ...utils import operators as utils_ops
from ..stream_param_holder import StreamParamHolder

__all__ = ('StreamParser',)


logger = logging.getLogger(__name__)


class StreamParser:
    def __init__(
        self, stream_param_holder: StreamParamHolder, *, ignore_eof: bool = False
    ) -> None:
        self._stream_param_holder = stream_param_holder
        self._ignore_eof = ignore_eof

    def __call__(self, source: Observable[io.RawIOBase]) -> FLVStream:
        return source.pipe(  # type: ignore
            flv_ops.parse(ignore_eof=self._ignore_eof, backup_timestamp=True),
            ops.do_action(on_error=self._before_retry),
            utils_ops.retry(should_retry=self._should_retry),
        )

    def _should_retry(self, exc: Exception) -> bool:
        if isinstance(exc, (EOFError, FlvDataError)):
            return True
        else:
            return False

    def _before_retry(self, exc: Exception) -> None:
        try:
            raise exc
        except EOFError:
            logger.debug(repr(exc))
        except FlvDataError:
            logger.warning(f'Failed to parse stream: {repr(exc)}')
            if not self._stream_param_holder.use_alternative_stream:
                self._stream_param_holder.use_alternative_stream = True
            else:
                self._stream_param_holder.use_alternative_stream = False
                self._stream_param_holder.rotate_api_platform()
        except Exception:
            pass