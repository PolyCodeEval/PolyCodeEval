FROM scratch
COPY datasets/cpp /data/cpp
COPY docs /data/docs
CMD ["/bin/sh"]
