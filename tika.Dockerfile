FROM eclipse-temurin:17-jre-jammy
ENV TIKA_VERSION=2.9.1
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -fsSL -o /opt/tika-server.jar \
    "https://archive.apache.org/dist/tika/${TIKA_VERSION}/tika-server-standard-${TIKA_VERSION}.jar" \
 && rm -rf /var/lib/apt/lists/*
EXPOSE 9998
HEALTHCHECK --interval=10s --timeout=5s --retries=12 \
  CMD curl -sf http://localhost:9998/tika || exit 1
ENTRYPOINT ["java","-jar","/opt/tika-server.jar","-p","9998","--host","0.0.0.0"]
