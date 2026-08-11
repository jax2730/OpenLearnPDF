void mainImage(out vec4 fragColor, in vec2 fragCoord)
{
    vec2 uv = (2.0 * fragCoord - iResolution.xy) / iResolution.y;
    float radiusSquared = dot(uv, uv);
    if (radiusSquared > 1.0)
    {
        fragColor = vec4(0.025, 0.03, 0.04, 1.0);
        return;
    }

    vec3 n = normalize(vec3(uv, sqrt(max(0.0, 1.0 - radiusSquared))));
    vec3 l = normalize(vec3(-0.45, 0.65, 0.75));
    vec3 v = vec3(0.0, 0.0, 1.0);
    vec3 surface = vec3(0.45, 0.50, 0.38);
    vec3 cool = vec3(0.0, 0.0, 0.55) + 0.25 * surface;
    vec3 warm = vec3(0.3, 0.3, 0.0) + 0.25 * surface;
    float t = clamp((dot(n, l) + 1.0) * 0.5, 0.0, 1.0);
    vec3 reflected = reflect(-l, n);
    float s = smoothstep(0.94, 0.985, max(dot(reflected, v), 0.0));
    vec3 shaded = mix(mix(cool, warm, t), vec3(1.0), s);

    fragColor = vec4(shaded, 1.0);
}
