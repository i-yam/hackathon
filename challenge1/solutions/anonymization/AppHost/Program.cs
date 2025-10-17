using Aspire.Hosting;
using Projects;

var builder = DistributedApplication.CreateBuilder(args);

builder.AddContainer("ollama", "ollama/ollama")
    .WithBindMount("ollama_data", "/root/.ollama");

builder.AddProject<DocumentReader>("documentreader");

builder.Build().Run();
