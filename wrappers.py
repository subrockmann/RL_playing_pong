import numpy as np
# import os
# os.environ.setdefault('PATH', '')
from collections import deque
import gym
from gym import spaces
import cv2
# cv2.ocl.setUseOpenCL(False)
# from .wrappers import TimeLimit

class PreProcessPongFrame(gym.ObservationWrapper):
    def __init__(self, env=None):
        super(PreProcessPongFrame, self).__init__(env)
        self.observation_space = gym.spaces.Box(low=0, high=255,
                                                shape=(84, 84, 1), dtype=np.uint8)

    def observation(self, obs):
        #return PreProcessPongFrame.process(obs)
        return PreProcessPongFrame.preprocess_frame(obs)

    @staticmethod
    def process(frame):

        new_frame = np.reshape(frame, frame.shape).astype(np.float32)

        new_frame = 0.299*new_frame[:, :, 0] + 0.587*new_frame[:, :, 1] + 0.114*new_frame[:, :, 2]

        new_frame = new_frame[35:195:2, ::2].reshape(80, 80, 1)

        return new_frame.astype(np.uint8)
    def preprocess_frame(image, shape=(84,84)):

        image = image.astype(np.uint8) # required for cv2
        image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        cropped_image = image[34:34+160, :160] # remove scores
        cropped_image = cv2.resize(cropped_image, shape, interpolation = cv2.INTER_NEAREST) # INTER_AREA
        cropped_image= cropped_image.reshape((*shape, 1))
        return cropped_image





class WarpFrame(gym.ObservationWrapper):
    def __init__(self, env, width=84, height=84, grayscale=True, dict_space_key=None):
        """
        Warp frames to 84x84 as done in the Nature paper and later work.
        If the environment uses dictionary observations, `dict_space_key` can be specified which indicates which
        observation should be warped.
        """
        super().__init__(env)
        self._width = width
        self._height = height
        self._grayscale = grayscale
        self._key = dict_space_key
        if self._grayscale:
            num_colors = 1
        else:
            num_colors = 3

        new_space = gym.spaces.Box(
            low=0,
            high=255,
            shape=(self._height, self._width, num_colors),
            dtype=np.uint8,
        )
        if self._key is None:
            original_space = self.observation_space
            self.observation_space = new_space
        else:
            original_space = self.observation_space.spaces[self._key]
            self.observation_space.spaces[self._key] = new_space
        assert original_space.dtype == np.uint8 and len(original_space.shape) == 3

    def observation(self, obs):
        if self._key is None:
            frame = obs
        else:
            frame = obs[self._key]

        if self._grayscale:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        frame = cv2.resize(
            frame, (self._width, self._height), interpolation=cv2.INTER_AREA
        )
        if self._grayscale:
            frame = np.expand_dims(frame, -1)

        if self._key is None:
            obs = frame
        else:
            obs = obs.copy()
            obs[self._key] = frame
        return obs



# taken from https://github.com/openai/baselines/blob/master/baselines/common/atari_wrappers.py

class LazyFrames(object):
    def __init__(self, frames):
        """This object ensures that common frames between the observations are only stored once.
        It exists purely to optimize memory usage which can be huge for DQN's 1M frames replay
        buffers.
        This object should only be converted to numpy array before being passed to the model.
        You'd not believe how complex the previous solution was."""
        self._frames = frames
        self._out = None

    def _force(self):
        if self._out is None:
            self._out = np.concatenate(self._frames, axis=-1)
            self._frames = None
        return self._out

    def __array__(self, dtype=None):
        out = self._force()
        if dtype is not None:
            out = out.astype(dtype)
        return out

    def __len__(self):
        return len(self._force())

    def __getitem__(self, i):
        return self._force()[i]

    def count(self):
        frames = self._force()
        return frames.shape[frames.ndim - 1]

    def frame(self, i):
        return self._force()[..., i]


class FrameStack(gym.Wrapper):
    def __init__(self, env, k):
        """Stack k last frames.
        Returns lazy array, which is much more memory efficient.
        See Also
        --------
        baselines.common.atari_wrappers.LazyFrames
        """
        gym.Wrapper.__init__(self, env)
        self.k = k
        self.frames = deque([], maxlen=k)
        shp = env.observation_space.shape
        self.observation_space = spaces.Box(low=0, high=255, shape=(shp[:-1] + (shp[-1] * k,)), dtype=env.observation_space.dtype)

    def reset(self):
        ob = self.env.reset()
        for _ in range(self.k):
            self.frames.append(ob)
        return self._get_ob()

    def step(self, action):
        ob, reward, done, info = self.env.step(action)
        self.frames.append(ob)
        return self._get_ob(), reward, done, info

    def _get_ob(self):
        assert len(self.frames) == self.k
        return LazyFrames(list(self.frames))