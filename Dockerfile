FROM debian:bookworm-slim

RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    gcc gcc-arm-none-eabi libnewlib-arm-none-eabi binutils-arm-none-eabi make \
    python3 python3-dev python3-pip libffi-dev git ca-certificates >/dev/null
RUN pip3 install --break-system-packages -q \
    "cffi==1.17.1" "greenlet>=3" "Jinja2==3.1.4" markupsafe pyserial paho-mqtt numpy

ARG U1_KLIPPER_REF=93cb12faebf6e74c51bbc5f0be66e95124af14c8
RUN git clone -q https://github.com/Snapmaker/u1-klipper.git /opt/klipper \
    && git -C /opt/klipper checkout -q "$U1_KLIPPER_REF"
WORKDIR /opt/klipper
RUN mkdir -p /opt/dicts && for c in at32f403a_config at32f415_config klippy_mcu_config; do \
      make -s clean >/dev/null 2>&1; cp "lava/$c" .config; make -s olddefconfig >/dev/null 2>&1; \
      make -s -j8 out/klipper.dict >/dev/null 2>&1 || make -s -j8 2>&1 | tail -3; \
      cp out/klipper.dict "/opt/dicts/$c.dict"; \
    done
RUN cd klippy/chelper && gcc -Wall -g -O2 -shared -fPIC -flto -fwhole-program \
    -fno-use-linker-plugin -o c_helper.so pyhelper.c serialqueue.c stepcompress.c \
    itersolve.c trapq.c pollreactor.c msgblock.c trdispatch.c kin_*.c
RUN python3 -c "import sys;sys.path.insert(0,'klippy');import chelper;chelper.get_ffi()"

COPY tests/firmware /app/firmware
WORKDIR /work
ENTRYPOINT ["python3", "/app/firmware/run.py"]
