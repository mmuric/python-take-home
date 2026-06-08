# Question 1 — Decisions

When we are talking about differences between `stage` and `prod` environments, we are talking about cross-environment differences, while when we are talking about files, environment variables, and remote APIs, we are talking about cross-source differences. We use a manifest file to define environments and, inside each environment, the sources of configuration keys and values. The `environments.yaml` manifest file is located in the root of the project and is loaded during bootstrap. In the manifest file, we define a priority for every environment and every source inside an environment. This helps when merging environments into the final config, and a higher priority number means that value will be preserved in the final merge.

## 1. Which configuration sources did you support and why? What did you exclude?

I excluded remote APIs. Testing them would require an additional service or mocked responses representing an environment. It seemed like overengineering for this question.

I used environment variables as the primary source for configuration key-value pairs. This is the most common runtime configuration mechanism and is also the recommended way to handle and store configuration according to the 12-factor app methodology. The second source is YAML files. This format is commonly used when declarative configuration and nested structures are needed. It has become a standard way of handling configuration in enterprise applications. Finally, I used Fernet to encrypt key-value pairs inside files, which simulates a Vault-like source. This source should contain all sensitive configuration values in the system. Using a real Vault solution such as HashiCorp Vault or HCP Vault would be too large in scope for this project.

## 2. What are your precedence rules and why? What alternatives did you consider?

As a first step, using the manifest file, we load every environment, every source, and the corresponding key-value mappings. While loading environment variables from non-sensitive data sources, we check key names and try to determine whether they may represent sensitive data that should be stored in Vault. If we detect such data, we create violations (records that stop the merge process). The goal of these violations is to prevent sensitive data from leaking into common sources.

Next, we merge configuration values across sources. The source precedence is:

`vault (40) > env (30) > yaml (10)`

After that, we merge across environments. The environment precedence is:

`prod (100) > stage (40)`

This means that `production.vault` has a priority of `140`, which beats `stage.vault` with a priority of `80`. The summed-priority mechanism preserves the hierarchy within an environment while allowing the target environment to win in cross-environment conflicts.

Alternatives considered:

1. Manifest without priorities — rejected because the first environment loaded would win in the final merge.
2. List-ordered convention — rejected because it is too implicit.

So the final precedence rules are:

load manifest -> load sources -> merge sources based on priority from manifest -> merge environments based on priority from manifest -> final JSON

## 3. How do you define "conflict"? Give one example that is a conflict and one that is not.

We defined two types of conflicts:

1. Conflict across sources — when the same key is discovered in different sources within the same environment, and the values differ, we consider this a conflict. For example, if `worker_count` exists in both a YAML file and environment variables with different values, we consider this a conflict. If the values are identical across different sources, we do not consider this a conflict.

2. Drift across environments — when the same key is discovered in different environments and has different values, we consider this a conflict that we call drift (e.g., `database.host` is `db-staging.internal` in `staging` versus `db-prod.internal` in `production`). When the values are the same, we do not consider this a drift.

Both of these are surfaced in the conflict report, and the operator can distinguish them by reading the origin label (`environment.source` pairs).

## 4. How do you handle source failures? Fail entirely or proceed partially? Why?

We fail entirely on any source unavailability. Required and optional sources are currently treated uniformly. I considered using the `required` flag in the manifest to explicitly fail only when a required source is unavailable, but this is not currently honored in `cmd_merge`, which results in a failure whenever any source is unavailable.

The trade-off is predictable behavior and no degraded output, but the downside is that the system currently treats all sources as required.

## 5. What did you skip or simplify? What would you improve with 10 more hours?

One thing that was skipped was differentiated handling when a source is missing. We already have a `required` parameter in the manifest, and I would extend `cmd_merge` to honor it. With this improvement, we could proceed partially when a source is not required and fail only when required sources are unavailable.

The second improvement would be better heuristics for detecting sensitive configuration values. At the moment, I use a naive approach based on key names. For example, `password_reset_url` would be considered a violation because it contains the word `password`. A better approach would be to use regular expressions with word boundaries and more precise matching rules.

The `diff` command is functionally almost identical to the `merge` command. The only difference is that it does not generate the final JSON file. It should be extended to provide a clearer comparison between environments and possibly support ignoring expected divergences (for example, `stage` and `prod` may intentionally have different database URLs).