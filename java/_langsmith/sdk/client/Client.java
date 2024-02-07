package _langsmith.sdk.client;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

import _langsmith.sdk.models.*;
import _langsmith.sdk.util.Utils;

public class Client {
    private final String apiUrl;
    private final String apiKey;
    private final HttpClient httpClient;

    public Client(String apiUrl, String apiKey) {
        this.apiUrl = apiUrl;
        this.apiKey = apiKey;
        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_2)
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();
    }

    public CompletableFuture<Run> createRun(CreateRunParams runParams) {
        return sendAsyncRequest("/runs", Utils.toJson(runParams), "POST")
                .thenApply(response -> Utils.fromJson(response.body(), Run.class));
    }

    public CompletableFuture<Void> batchIngestRuns(BatchIngestRunParams params) {
        return sendAsyncRequest("/runs/batch", Utils.toJson(params), "POST")
                .thenApply(response -> null);
    }

    public CompletableFuture<Void> updateRun(String runId, RunUpdate runUpdate) {
        String validatedRunId = ensureUuid(runId, "runId");
        return sendAsyncRequest("/runs/" + validatedRunId, Utils.toJson(runUpdate), "PATCH")
                .thenApply(response -> null);
    }

    private CompletableFuture<HttpResponse<String>> sendAsyncRequest(String path, String requestBody, String method) {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(apiUrl + path))
                .timeout(java.time.Duration.ofMinutes(2))
                .header("Content-Type", "application/json")
                .header("x-api-key", apiKey)
                .method(method, HttpRequest.BodyPublishers.ofString(requestBody))
                .build();

        return httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(response -> {
                    Utils.raiseForStatus(response, method.toLowerCase());
                    return response;
                });
    }

    private String ensureUuid(String id, String parameterName) {
        try {
            // This will throw IllegalArgumentException if id is not a valid UUID
            UUID.fromString(id);
            return id;
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("Invalid UUID for " + parameterName + ": " + id, e);
        }
    }
}
