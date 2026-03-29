# OpenClaw Skill Integration

This directory contains the OpenClaw skill manifest for ACloudViewer MCP integration.

## File: `openclaw-skill.json`

This is the **canonical version** of the ACloudViewer OpenClaw skill manifest. It is automatically packaged with the `cli-anything-acloudviewer` Python package when published to PyPI.

### Purpose

The skill manifest enables OpenClaw (and other AI agent platforms) to discover and use the ACloudViewer MCP server with all 95+ tools for 3D point cloud and mesh processing.

### Usage in OpenClaw

Users can configure OpenClaw to use this skill in two ways:

1. **Managed (ClawHub Marketplace)**:
   - Search for "acloudviewer" in the ClawHub marketplace
   - Toggle the skill on

2. **Self-Hosted**:
   ```bash
   pip install cli-anything-acloudviewer
   ```
   
   Then add to `openclaw.json`:
   ```json
   {
     "plugins": {
       "acloudviewer": {
         "command": "cli-anything-acloudviewer-mcp",
         "args": ["--mode", "auto"],
         "type": "mcp",
         "description": "3D point cloud and mesh processing with ACloudViewer (95+ tools)"
       }
     }
   }
   ```

### Version Synchronization

The `version` field in this file MUST match the version in `setup.py` to ensure consistency between the package and the skill manifest.

**Current version**: 3.1.0

### Related Documentation

- Full OpenClaw integration guide: [ACloudViewer/agent-integration/openclaw/README.md](https://github.com/Asher-1/ACloudViewer/tree/main/agent-integration/openclaw)
- MCP Server documentation: [CLI-Anything/acloudviewer/agent-harness/README.md](../README.md)
- Tool reference: [mcp_server.py](mcp_server.py)

### Maintenance

When updating this file:
1. Update the `version` field to match `setup.py`
2. Update `tools_count` if tools are added/removed
3. Update `tool_categories` to reflect new categories or tools
4. Sync the reference copy in the ACloudViewer repository (for documentation purposes)

### Reference Copy

A reference copy of this file is maintained at:
`ACloudViewer/agent-integration/openclaw/openclaw-skill.json`

This copy is for documentation and user reference only. All changes should be made to this canonical version first.
