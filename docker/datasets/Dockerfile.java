FROM scratch
COPY datasets/java /data/java
COPY docs /data/docs
CMD ["/bin/sh"]
