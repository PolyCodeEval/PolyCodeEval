FROM scratch
COPY datasets/javascript /data/javascript
COPY docs /data/docs
CMD ["/bin/sh"]
