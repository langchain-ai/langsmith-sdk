package langsmith.sdk.util;

import com.google.gson.Gson;
import java.net.http.HttpResponse;

public class Utils {
    private static final Gson gson = new Gson();

    public static String toJson(Object obj) {
        return gson.toJson(obj);
    }

    public static <T> T fromJson(String json, Class<T> classOfT) {
        return gson.fromJson(json, classOfT);
    }

    public static void raiseForStatus(HttpResponse<String> response, String operation) throws Exception {
        if (response.statusCode() >= 300) {
            throw new Exception(String.format(
                "Failed to %s: %d %s %s",
                operation,
                response.statusCode(),
                response.version(),
                response.body()
            ));
        }
    }
}
