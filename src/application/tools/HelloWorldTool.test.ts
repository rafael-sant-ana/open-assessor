import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import HelloWorldTool from './HelloWorldTool.js';

describe('HelloWorldTool', () => {
    const tool = new HelloWorldTool();

    it('greets the world by default', async () => {
        assert.equal(await tool.execute({}), 'Hello, World! (sent by the hello_world tool)');
    });

    it('greets the given name', async () => {
        assert.equal(await tool.execute({ name: ' Rafa ' }), 'Hello, Rafa! (sent by the hello_world tool)');
    });

    it('falls back to the world when name is not a usable string', async () => {
        assert.equal(await tool.execute({ name: 42 }), 'Hello, World! (sent by the hello_world tool)');
        assert.equal(await tool.execute({ name: '  ' }), 'Hello, World! (sent by the hello_world tool)');
    });
});
