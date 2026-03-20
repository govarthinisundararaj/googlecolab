import yaml
import sys

def parse_cpu(cpu):
    return int(cpu.replace("m", ""))  # "250m" → 250

def parse_memory(mem):
    if mem.endswith("Mi"):
        return int(mem.replace("Mi", ""))
    if mem.endswith("Gi"):
        return int(mem.replace("Gi", "")) * 1024
    return int(mem)

# Load files
with open("deployment.yaml") as f:
    dep = yaml.safe_load(f)

with open("rules.yaml") as f:
    rules = yaml.safe_load(f)

errors = []

spec = dep.get("spec", {})
template = spec.get("template", {})
pod_spec = template.get("spec", {})
containers = pod_spec.get("containers", [])

# --- Replicas ---
replicas = spec.get("replicas", 1)
r_rules = rules["deployment"]["replicas"]

if not (r_rules["min"] <= replicas <= r_rules["max"]):
    errors.append(f"Replicas {replicas} خارج allowed range")

# --- Strategy ---
strategy = spec.get("strategy", {})
s_rules = rules["deployment"]["strategy"]

if strategy.get("type") != s_rules["type"]:
    errors.append("Strategy must be RollingUpdate")

ru = strategy.get("rollingUpdate", {})
if ru.get("maxUnavailable") != s_rules["rollingUpdate"]["maxUnavailable"]:
    errors.append("Invalid maxUnavailable")

if ru.get("maxSurge") != s_rules["rollingUpdate"]["maxSurge"]:
    errors.append("Invalid maxSurge")

# --- Containers ---
for c in containers:
    name = c.get("name", "unknown")

    # Image
    image = c.get("image", "")
    if rules["container"]["image"]["disallowLatest"] and image.endswith(":latest"):
        errors.append(f"{name}: latest tag not allowed")

    # Resources
    res = c.get("resources", {})
    if rules["container"]["resources"]["required"] and not res:
        errors.append(f"{name}: resources missing")
    else:
        req = res.get("requests", {})
        cpu = parse_cpu(req.get("cpu", "0m"))
        mem = parse_memory(req.get("memory", "0Mi"))

        cpu_rules = rules["container"]["resources"]["requests"]["cpu"]
        mem_rules = rules["container"]["resources"]["requests"]["memory"]

        if not (parse_cpu(cpu_rules["min"]) <= cpu <= parse_cpu(cpu_rules["max"])):
            errors.append(f"{name}: CPU request out of range")

        if not (parse_memory(mem_rules["min"]) <= mem <= parse_memory(mem_rules["max"])):
            errors.append(f"{name}: Memory request out of range")

    # Liveness Probe
    l_probe = c.get("livenessProbe", {})
    l_rules = rules["container"]["probes"]["liveness"]

    if l_rules["required"] and not l_probe:
        errors.append(f"{name}: missing livenessProbe")
    else:
        delay = l_probe.get("initialDelaySeconds", 0)
        if not (l_rules["initialDelaySeconds"]["min"] <= delay <= l_rules["initialDelaySeconds"]["max"]):
            errors.append(f"{name}: liveness initialDelaySeconds invalid")

    # Readiness Probe
    r_probe = c.get("readinessProbe", {})
    r_rules = rules["container"]["probes"]["readiness"]

    if r_rules["required"] and not r_probe:
        errors.append(f"{name}: missing readinessProbe")

    # Ports
    ports = c.get("ports", [])
    allowed_ports = rules["container"]["ports"]["allowed"]

    if rules["container"]["ports"]["required"] and not ports:
        errors.append(f"{name}: no ports defined")
    else:
        for p in ports:
            if p.get("containerPort") not in allowed_ports:
                errors.append(f"{name}: port {p.get('containerPort')} not allowed")

# --- Result ---
if errors:
    print("❌ Validation Failed:\n")
    for e in errors:
        print("-", e)
    sys.exit(1)
else:
    print("✅ Deployment Valid")
