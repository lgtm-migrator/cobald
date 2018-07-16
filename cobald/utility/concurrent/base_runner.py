import logging
import threading

from ...utility.debug import NameRepr


class BaseRunner(object):
    flavour = None

    def __init__(self):
        self._logger = logging.getLogger('cobald.runtime.runner.%s' % NameRepr(self.flavour))
        self._payloads = []
        self._lock = threading.Lock()
        self.running = threading.Event()

    def register_payload(self, payload):
        """
        Register ``payload`` for asynchronous execution

        This runs ``payload`` as an orphaned background task as soon as possible.
        It is an error for ``payload`` to return or raise anything without handling it.
        """
        self._payloads.append(payload)

    def run_payload(self, payload):
        """
        Register ``payload`` for synchronous execution

        This runs ``payload`` as soon as possible, blocking until completion.
        Should ``payload`` return or raise anything, it is propagated to the caller.
        """
        raise NotImplementedError

    def run(self):
        """
        Execute all current and future payloads

        Blocks and executes payloads until :py:meth:`stop` is called.
        It is an error for any orphaned payload to return or raise.
        """
        self._logger.info('runner started: %s', self)
        try:
            with self._lock:
                assert not self.running.set(), 'cannot re-run: %s' % self
                self.running.set()
            self._run()
        except Exception:
            self._logger.error('runner aborted: %s', self)
            raise
        else:
            self._logger.info('runner stopped: %s', self)
        finally:
            self.running.clear()

    def _run(self):
        raise NotImplementedError

    def stop(self):
        """Stop execution of all current and future payloads"""
        self.running.clear()


class OrphanedReturn(Exception):
    """A runnable returned a value without anyone to receive it"""
    def __init__(self, who, value):
        super().__init__('no caller to receive %s from %s' % (value, who))
        self.who = who
        self.value = value
