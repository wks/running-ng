from pathlib import Path
from typing import Any, Dict, List, Optional
from running.benchmark import JavaBenchmark, BinaryBenchmark
import logging
from running.util import register

__DRY_RUN = False


def is_dry_run():
    global __DRY_RUN
    return __DRY_RUN


def set_dry_run(val: bool):
    global __DRY_RUN
    __DRY_RUN = val


class BenchmarkSuite(object):
    CLS_MAPPING: Dict[str, Any]
    CLS_MAPPING = {}

    def __init__(self, name: str, **kwargs):
        self.name = name

    def __str__(self) -> str:
        return "Benchmark Suite {}".format(self.name)

    def get_benchmark(self, bm_name: str) -> Any:
        raise NotImplementedError()

    @staticmethod
    def from_config(name: str, config: Dict[str, str]) -> Any:
        return BenchmarkSuite.CLS_MAPPING[config["type"]](name=name, **config)

    def is_oom(self, _output: str) -> bool:
        raise NotImplementedError

    def get_minheap(self, _bm_name: str) -> int:
        raise NotImplementedError

    def get_timeout(self, _bm_name: str) -> Optional[int]:
        # No timeout by default
        return None

    def is_passed(self, _output: str) -> bool:
        raise NotImplementedError


@register(BenchmarkSuite)
class BinaryBenchmarkSuite(BenchmarkSuite):
    def __init__(self, programs: Dict[str, str], **kwargs):
        super().__init__(**kwargs)
        self.programs = {k: Path(v) for k, v in programs.items()}
        self.timeout = kwargs.get("timeout")

    def get_benchmark(self, bm_name: str) -> 'BinaryBenchmark':
        return BinaryBenchmark(self.programs[bm_name], suite_name=self.name, bm_name=bm_name)

    def is_oom(self, _output: str) -> bool:
        return False

    def get_timeout(self, _bm_name: str) -> Optional[int]:
        # FIXME have per benchmark timeout
        return self.timeout

    def get_minheap(self, _bm_name: str) -> int:
        logging.warning("miheap is not respected for BinaryBenchmarkSuite")
        return 0

    def is_passed(self, _output: str) -> bool:
        # FIXME no generic way to know
        return True


class JavaBenchmarkSuite(BenchmarkSuite):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_minheap(self, bm_name: str) -> int:
        raise NotImplementedError()

    def get_timeout(self, bm_name: str) -> Optional[int]:
        raise NotImplementedError()

    def is_oom(self, output: str) -> bool:
        for pattern in ["Allocation Failed", "OutOfMemoryError", "ran out of memory"]:
            if pattern in output:
                return True
        return False


@register(BenchmarkSuite)
class DaCapo(JavaBenchmarkSuite):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.release = kwargs["release"]
        if self.release not in ["2006", "9.12", "evaluation"]:
            logging.info(
                "DaCapo release {} not recongized".format(self.release))
        self.path: Path
        self.path = Path(kwargs["path"])
        if not self.path.exists():
            logging.info("DaCapo jar {} not found".format(self.path))
        self.minheap = kwargs.get("minheap", {})
        try:
            self.timing_iteration = int(kwargs.get("timing_iteration"))
        except TypeError:
            logging.warning(
                "Timing iteration not set for DaCapo {}, use default value 3".format(self.path))
            self.timing_iteration = 3
        self.callback = kwargs.get("callback")
        self.timeout = kwargs.get("timeout")

    def __str__(self) -> str:
        return "{} DaCapo {} {}".format(super().__str__(), self.release, self.path)

    def get_benchmark(self, bm_name: str) -> 'JavaBenchmark':
        if self.callback:
            cp = [str(self.path)]
            progam_args = ["Harness", "-c", self.callback]
        else:
            cp = []
            progam_args = ["-jar", str(self.path)]
        progam_args.extend(["-n", str(self.timing_iteration), bm_name])
        return JavaBenchmark([], progam_args, cp, suite_name=self.name, bm_name=bm_name)

    def get_minheap(self, bm_name: str) -> int:
        if bm_name not in self.minheap:
            logging.warn("Minheap for {} of {} not set".format(bm_name, self))
            return 4096
        return self.minheap[bm_name]

    def get_timeout(self, _bm_name: str) -> int:
        # FIXME have per benchmark timeout
        return self.timeout

    def is_passed(self, output: str) -> bool:
        return "PASSED" in output
