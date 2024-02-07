package langsmith.sdk.models;

import java.util.Map;

public class Run {
    private String id;
    // Other properties...
}

public class CreateRunParams {
    private String name;
    private Map<String, Object> inputs;
    // Other properties...
    // Constructors, getters, setters...
}

public class RunUpdate {
    // Properties for run update...
    // Constructors, getters, setters...
}

public class BatchIngestRunParams {
    private List<CreateRunParams> runCreates;
    private List<RunUpdate> runUpdates;
    // Constructors, getters, setters...
}
