FROM scratch
COPY datasets/go /data/go
COPY docs /data/docs
CMD ["/bin/sh"]
