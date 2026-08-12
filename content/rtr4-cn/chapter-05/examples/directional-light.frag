#version 450

layout(location = 0) out vec4 outColor;

void main() {
    vec2 uv = gl_FragCoord.xy / vec2(800.0, 600.0) * 2.0 - 1.0;
    uv.x *= 800.0 / 600.0;
    float radius2 = dot(uv, uv);
    if (radius2 > 1.0) {
        discard;
    }

    vec3 normal = normalize(vec3(uv, sqrt(1.0 - radius2)));
    vec3 lightDirection = normalize(vec3(-0.5, 0.7, 0.8));
    float directLight = max(dot(normal, lightDirection), 0.0);
    vec3 surfaceColor = vec3(0.35, 0.62, 0.9);
    vec3 ambient = 0.08 * surfaceColor;
    outColor = vec4(ambient + directLight * surfaceColor, 1.0);
}
